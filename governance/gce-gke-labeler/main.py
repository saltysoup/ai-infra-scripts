# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# [START functions_label_gce_gke_instance]
import json
from datetime import datetime, timedelta

from google.api_core.exceptions import GoogleAPIError
from google.cloud import compute_v1
from google.cloud.compute_v1.types import compute

instances_client = compute_v1.InstancesClient()

# CloudEvent function that labels newly-created GCE instances
# with the entity (user or service account) that created them.
#
# @param {object} cloudevent A CloudEvent containing the Cloud Audit Log entry.
# @param {object} cloudevent.data.protoPayload The Cloud Audit Log entry.
def label_gce_gke_instance(data: dict,event: dict) -> None:
    # Decode bytes to string
    cloudevent_str = data.decode('utf-8')
    # Parse JSON string to dictionary
    cloudevent = json.loads(cloudevent_str)

    '''
    example cloudevent = {'@type': 'type.googleapis.com/google.events.cloud.audit.v1.LogEntryData', 'protoPayload': {'authenticationInfo': {'principalEmail': 'ikwak@google.com', 'principalSubject': 'user:ikwak@google.com'}, 'requestMetadata': {'callerIp': '163.53.146.16', 'callerSuppliedUserAgent': 'google-cloud-sdk gcloud/444.0.0 command/gcloud.compute.instances.create invocation-id/71cb8723d49f4ef8b82260134ad74f81 environment/None environment-version/None client-os/LINUX client-os-ver/6.6.50 client-pltf-arch/x86_64 interactive/True from-script/False python/3.9.16 term/xterm-256color (Linux 6.6.50-05090-g02ec56928355),gzip(gfe)', 'requestAttributes': {}, 'destinationAttributes': {}}, 'serviceName': 'compute.googleapis.com', 'methodName': 'v1.compute.instances.insert', 'resourceName': 'projects/gpu-launchpad-playground/zones/us-central1-a/instances/test1', 'serviceData': {}, 'request': {'@type': 'type.googleapis.com/compute.instances.insert'}}, 'insertId': 'paohsne1bsvs', 'resource': {'type': 'gce_instance', 'labels': {'instance_id': '1767399794411435844', 'project_id': 'gpu-launchpad-playground', 'zone': 'us-central1-a'}}, 'timestamp': '2024-12-04T12:23:12.407742Z', 'severity': 'NOTICE', 'labels': {'compute.googleapis.com/root_trigger_id': '53647822-96b6-41d9-9d9e-26c4602659ab'}, 'logName': 'projects/gpu-launchpad-playground/logs/cloudaudit.googleapis.com%2Factivity', 'operation': {'id': 'operation-1733314986767-62870d811f398-95d85d80-5fc19abc', 'producer': 'compute.googleapis.com', 'last': True}, 'receiveTimestamp': '2024-12-04T12:23:13.088396054Z'}
    '''
    print("running label_gce_gke_instance with event: {}".format(cloudevent))
    # Extract parameters from the CloudEvent + Cloud Audit Log data
    payload = cloudevent['protoPayload']
    creator = payload['authenticationInfo']['principalEmail']

    # Get relevant VM instance details from the cloudevent's `subject` property
    # Example value:
    #   compute.googleapis.com/projects/<PROJECT_ID>/zones/<ZONE_ID>/instances/<INSTANCE_NAME>
    #instance_params = cloudevent["subject"].split("/")
    instance_project = cloudevent['resource']['labels']['project_id']
    instance_zone = cloudevent['resource']['labels']['zone']
    instance_name = cloudevent['protoPayload']['resourceName'].split('/')[-1]

    # Format the 'creator' parameter to match GCE label validation requirements
    creator = creator.replace("@", "_")
    creator = creator.replace(".", "_")
    
    # workaround label value max limit of 63 char
    if len(creator) > 63:
        creator = creator.split('iam')[0]


    # Get the newly-created VM instance's label fingerprint
    # This is required by the Compute Engine API to prevent duplicate labels
    instance = instances_client.get(
        project=instance_project, zone=instance_zone, instance=instance_name
    )

    # Generate created-by, created-date, stop-by, delete-by labels
    created_date = datetime.now().strftime("%Y%m%d")
    stop_by = (datetime.now() + timedelta(days=7)).strftime("%Y%m%d")
    delete_by = (datetime.now() + timedelta(days=30)).strftime("%Y%m%d")

    # Merge any existing labels with the new labels
    existing_labels = dict(instance.labels)
    governance_labels = {"created-by": creator, "created-date": created_date, "stop-by": stop_by, "delete-by": delete_by}
    merged_labels = {**existing_labels, **governance_labels}
    # Construct API call to label the VM instance with its creator
    request_init = {
        "project": instance_project,
        "zone": instance_zone,
        "instance": instance_name,
    }
    request_init[
        "instances_set_labels_request_resource"
    ] = compute.InstancesSetLabelsRequest(
        label_fingerprint=instance.label_fingerprint,
        labels=merged_labels
    )
    request = compute.SetLabelsInstanceRequest(request_init)

    # Perform instance-labeling API call
    try:
        instances_client.set_labels_unary(request)
        print(f"Labelled VM instance {instance_name} with created-by: {creator}, created-date: {created_date}, stop-by: {stop_by}, delete-by: {delete_by}")
    except GoogleAPIError as e:
        # Swallowing the exception means failed invocations WON'T be retried
        print("Label operation failed", e)

        # Uncomment the line below to retry failed invocations.
        # (You'll also have to enable retries in Cloud Functions itself.)
        raise e
    return


# [END functions_label_gce_gke_instance]
