#!/bin/bash

# Script to upload secrets from .env file to AWS Secrets Manager
# Usage: ./set-secrets.sh [path-to-.env-file]

set -e

# Configuration - update these to match your Terraform variables
APP_FAMILY="dpa"
APP_NAME="dpa-ai-agent-api"
ENV_NAME="dev-snapshot"
AWS_REGION="us-west-2"

# Path to .env file (default to current directory)
ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at: $ENV_FILE"
    echo "Usage: $0 [path-to-.env-file]"
    exit 1
fi

echo "Reading secrets from: $ENV_FILE"
echo "Target AWS Region: $AWS_REGION"
echo "Secret path prefix: /${APP_FAMILY}/${APP_NAME}/${ENV_NAME}/"
echo ""

# Function to convert SCREAMING_SNAKE_CASE to kebab-case
to_kebab_case() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | tr '_' '-'
}

# Read .env file and process each line
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue

    # Trim whitespace
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)

    # Skip if value is empty
    if [ -z "$value" ]; then
        echo "⚠️  Skipping $key (empty value)"
        continue
    fi

    # Convert key to kebab-case for secret name
    secret_name=$(to_kebab_case "$key")
    secret_id="/${APP_FAMILY}/${APP_NAME}/${ENV_NAME}/${secret_name}"

    echo "Setting secret: $secret_id"

    # Set the secret value
    aws secretsmanager put-secret-value \
        --secret-id "$secret_id" \
        --secret-string "$value" \
        --region "$AWS_REGION" \
        --output json > /dev/null

    if [ $? -eq 0 ]; then
        echo "✓ Successfully set $key"
    else
        echo "✗ Failed to set $key"
    fi

    echo ""

done < "$ENV_FILE"

echo "Done! All secrets have been updated in AWS Secrets Manager."
