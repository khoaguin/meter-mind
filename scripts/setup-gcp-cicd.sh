#!/usr/bin/env bash
# One-time GCP bootstrap for MeterMind CI/CD (Cloud Run + Artifact Registry via
# GitHub Actions with Workload Identity Federation — no service-account keys).
#
# Run it once, from a machine authenticated as a project owner/editor:
#   gcloud auth login
#   ./scripts/setup-gcp-cicd.sh
#
# It is idempotent — re-running only fills in whatever is missing. At the end it
# prints the two values to add as GitHub repo secrets:
#   GCP_WORKLOAD_IDENTITY_PROVIDER
#   GCP_SERVICE_ACCOUNT_EMAIL
set -euo pipefail

# --- Config (edit if you fork/rename) ---------------------------------------
PROJECT_ID="ai-playground-458112"
REGION="asia-southeast1"
GITHUB_REPO="khoaguin/meter-mind"     # owner/repo
GITHUB_OWNER="${GITHUB_REPO%%/*}"

AR_REPO="meter-mind"                   # Artifact Registry docker repo
SA_NAME="gh-actions-deployer"          # deploying service account (impersonated by Actions)
POOL_ID="github-pool"
PROVIDER_ID="github-provider"
# ----------------------------------------------------------------------------

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Using project ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

echo "==> Enabling required APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  iam.googleapis.com

echo "==> Artifact Registry repo (${AR_REPO})"
gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="MeterMind container images"

echo "==> Deploying service account (${SA_EMAIL})"
gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="GitHub Actions deployer (MeterMind)"

echo "==> Granting deploy roles to ${SA_EMAIL}"
for ROLE in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None >/dev/null
done
# run.admin lets it deploy; serviceAccountUser lets it set the Cloud Run
# runtime SA (the default compute SA here); artifactregistry.writer lets it push.

echo "==> Workload Identity pool (${POOL_ID})"
gcloud iam workload-identity-pools describe "${POOL_ID}" --location=global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "${POOL_ID}" \
    --location=global \
    --display-name="GitHub Actions"

echo "==> OIDC provider (${PROVIDER_ID}) — scoped to owner ${GITHUB_OWNER}"
gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
  --location=global --workload-identity-pool="${POOL_ID}" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
    --location=global \
    --workload-identity-pool="${POOL_ID}" \
    --display-name="GitHub OIDC" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_OWNER}'"

POOL_FULL_ID="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"

echo "==> Letting ${GITHUB_REPO} impersonate ${SA_EMAIL}"
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_FULL_ID}/attribute.repository/${GITHUB_REPO}" >/dev/null

PROVIDER_RESOURCE="${POOL_FULL_ID}/providers/${PROVIDER_ID}"

cat <<EOF

============================================================
✅ Done. Add these as GitHub repo secrets
   (Settings → Secrets and variables → Actions → New repository secret):

GCP_WORKLOAD_IDENTITY_PROVIDER
${PROVIDER_RESOURCE}

GCP_SERVICE_ACCOUNT_EMAIL
${SA_EMAIL}

Or with the gh CLI:
  gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER -b "${PROVIDER_RESOURCE}" -R ${GITHUB_REPO}
  gh secret set GCP_SERVICE_ACCOUNT_EMAIL      -b "${SA_EMAIL}"          -R ${GITHUB_REPO}
============================================================
EOF
