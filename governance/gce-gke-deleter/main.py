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


# [START functions_delete_gce_gke_instance]
from __future__ import annotations
from typing import Any
from datetime import datetime
from google.cloud import compute_v1
from google.api_core.extended_operation import ExtendedOperation
from google.cloud import compute_v1
from google.cloud import container_v1
from google.cloud.container_v1 import types
import sys
import time


project_id='tpu-launchpad-playground'

instances_client = compute_v1.InstancesClient()
request = compute_v1.AggregatedListInstancesRequest(project=project_id)
gke_client = container_v1.ClusterManagerClient()

# CloudEvent function that labels newly-created GCE instances
# with the entity (user or service account) that created them.
#
# @param {object} cloudevent A CloudEvent containing the Cloud Audit Log entry.
# @param {object} cloudevent.data.protoPayload The Cloud Audit Log entry.

def list_instances(project_id):
    results = {}
    count = 0
    for zone, instances_in_zone in instances_client.aggregated_list(request=request):
        for instance in instances_in_zone.instances:
            key_name=f"instance{count}"
            results[key_name] = {"instance": instance.name, "zone": zone.split('zones/')[1]}
            count += 1
    return results

def get_delete_by_labels(project_id,instance_name,zone):
    # Get the newly-created VM instance's label fingerprint
    # This is required by the Compute Engine API to prevent duplicate labels
    instance = instances_client.get(
        project=project_id, instance=instance_name, zone=zone 
    )
    time_now = datetime.now().strftime("%Y%m%d")

    if 'delete-by' in instance.labels:
        if instance.labels['delete-by'] == time_now:
            print (f"Deleting instance {instance_name} in zone {zone} with delete time being {time_now}")
            
def wait_for_extended_operation(
    operation: ExtendedOperation, verbose_name: str = "operation", timeout: int = 300
) -> Any:
    """
    Waits for the extended (long-running) operation to complete.

    If the operation is successful, it will return its result.
    If the operation ends with an error, an exception will be raised.
    If there were any warnings during the execution of the operation
    they will be printed to sys.stderr.

    Args:
        operation: a long-running operation you want to wait on.
        verbose_name: (optional) a more verbose name of the operation,
            used only during error and warning reporting.
        timeout: how long (in seconds) to wait for operation to finish.
            If None, wait indefinitely.

    Returns:
        Whatever the operation.result() returns.

    Raises:
        This method will raise the exception received from `operation.exception()`
        or RuntimeError if there is no exception set, but there is an `error_code`
        set for the `operation`.

        In case of an operation taking longer than `timeout` seconds to complete,
        a `concurrent.futures.TimeoutError` will be raised.
    """
    result = operation.result(timeout=timeout)

    if operation.error_code:
        print(
            f"Error during {verbose_name}: [Code: {operation.error_code}]: {operation.error_message}",
            file=sys.stderr,
            flush=True,
        )
        print(f"Operation ID: {operation.name}", file=sys.stderr, flush=True)
        raise operation.exception() or RuntimeError(operation.error_message)

    if operation.warnings:
        print(f"Warnings during {verbose_name}:\n", file=sys.stderr, flush=True)
        for warning in operation.warnings:
            print(f" - {warning.code}: {warning.message}", file=sys.stderr, flush=True)

    return result


def delete_instance(project_id: str, instance_name: str, zone: str) -> None:
    """
    Deletes a running Google Compute Engine instance.
    Args:
        project_id: project ID or project number of the Cloud project your instance belongs to.
        zone: name of the zone your instance belongs to.
        instance_name: name of the instance your want to delete.
    """
    instance = instances_client.get(
        project=project_id, instance=instance_name, zone=zone 
    )
    time_now = datetime.now().strftime("%Y%m%d")

    if 'delete-by' in instance.labels:
        # check if delete date is same or before current date
        if datetime.strptime(instance.labels['delete-by'],'%Y%m%d') <= datetime.now():
            print (f"Deleting instance {instance_name} in zone {zone} for delete date being {time_now}")
            # check if instance is gke node and delete cluster
            if 'goog-gke-node' in instance.labels:
                name = f"projects/{project_id}/locations/{instance.labels['goog-k8s-cluster-location']}/clusters/{instance.labels['goog-k8s-cluster-name']}"
                delete_cluster(name)
            else:
                operation = instances_client.delete(
                    project=project_id, zone=zone, instance=instance_name
                )
                wait_for_extended_operation(operation, "instance deleting")
        else:
            delta = abs(datetime.strptime(instance.labels['delete-by'],"%Y%m%d") - datetime.now())
            print (f"Skipping instance {instance_name} as delete time is {delta.days} days away")
    else:
        print (f"Skipping instance {instance_name} as it has no delete date label")

def delete_cluster(name):
    """Deletes a  GKE cluster.

    Args:
        name: The name (project, location, cluster) of the cluster to delete. Specified in the format projects/*/locations/*/clusters/*.
    """

    # Construct the full name of the node pool.
    

    # Create a request to update the node pool size.
    request = types.DeleteClusterRequest(
        name=name
    )

    try:
        # Make the request to resize the node pool.
        operation = gke_client.delete_cluster(request=request)
        print(f"Delete cluster {name}. Operation: {operation.name}")

        # Wait for the operation to complete.
        while True:
            operation_request_name=name.split('clusters')[0] + f"operations/{operation.name}"
            operation = gke_client.get_operation(
                name=operation_request_name # format: projects/*/locations/*/operations/*
            )
            if operation.status == types.Operation.Status.DONE:
                print(f"Cluster '{name}' deleted successfully.")
                break
            elif operation.status == types.Operation.Status.ABORTED:
                print(f"Cluster deletion operation was aborted: {operation.error_message}")
                break
            elif operation.status == types.Operation.Status.RUNNING or operation.status == types.Operation.Status.PENDING:
                print(f"Waiting for delete operation to complete. Current status: {operation.status.name}")
                time.sleep(10) # Wait for 10 seconds before checking again.
            else:
                print(f"Cluster deletion failed: {operation.error_message}")
                break

    except Exception as e:
        print(f"An error occurred: {e}")

def delete_gce_gke_instance(data,event):
    print (f"running delete instance function with event: {event} and data: {data}")
    results = list_instances(project_id)
    for instance in results:
        print (f"Checking if {results[instance]['instance']} needs to be deleted")
        delete_instance(project_id,results[instance]['instance'],results[instance]['zone'])
    return

# [END functions_delete_gce_gke_instance]
