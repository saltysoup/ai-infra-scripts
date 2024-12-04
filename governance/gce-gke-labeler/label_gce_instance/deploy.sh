#!/bin/bash

REGION=us-central1

# enable APIs
gcloud services enable compute.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com eventarc.googleapis.com logging.googleapis.com pubsub.googleapis.com cloudfunctions.googleapis.com run.googleapis.com

# set IAM permission compute engine service account 
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects list --filter="project_id:$PROJECT_ID" --format='value(project_number)')

# Allow eventarc event receiever
gcloud projects add-iam-policy-binding $PROJECT_ID \
 --member serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
 --role roles/eventarc.eventReceiver
# Allow service account token creation
gcloud projects add-iam-policy-binding $PROJECT_ID \
 --member serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
 --role roles/run.invoker
# Allow compute instance adminn
gcloud projects add-iam-policy-binding $PROJECT_ID \
 --member serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
 --role roles/compute.instanceAdmin


gcloud functions deploy python-cal-function \
--gen2 \
--runtime=python312 \
--region=${REGION} \
--source=. \
--entry-point=label_gce_gke_instance \
--trigger-location=${REGION} \
--trigger-event-filters="type=google.cloud.audit.log.v1.written" \
--trigger-event-filters="serviceName=compute.googleapis.com" \
--trigger-event-filters="methodName=v1.compute.instances.insert" ##todo include gke events
