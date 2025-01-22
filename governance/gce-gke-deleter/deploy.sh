
REGION=us-central1

# enable APIs
gcloud services enable cloudscheduler.googleapis.com compute.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com eventarc.googleapis.com logging.googleapis.com pubsub.googleapis.com cloudfunctions.googleapis.com run.googleapis.com

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

# create pubsub for scheduling job
gcloud pubsub topics create delete-instance-event

# deploy cloud function
gcloud functions deploy gce-gke-deleter \
--gen2 \
--runtime=python312 \
--region=${REGION} \
--source=. \
--entry-point=delete_gce_gke_instance \
--trigger-location=${REGION} \
--trigger-topic=delete-instance-event

# create cloud scheduler job
gcloud scheduler jobs create pubsub delete-gce-gke-instances \
    --schedule '0 0 * * *' \
    --topic delete-instance-event \
    --message-body="daily VM delete checker" \
    --time-zone="UTC" \
    --location us-central1

# test
gcloud functions call gce-gke-deleter \
    --data '{"data":"foo"}'
