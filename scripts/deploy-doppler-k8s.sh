#!/bin/bash

# This script deploys the Doppler Kubernetes Operator and configures it for the Atheon AI project

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "kubectl is not installed. Please install it first."
    exit 1
fi

# Check if DOPPLER_SERVICE_TOKEN is set
if [ -z "$DOPPLER_SERVICE_TOKEN" ]; then
    echo "DOPPLER_SERVICE_TOKEN is not set. Please set it first:"
    echo "export DOPPLER_SERVICE_TOKEN=dp.st.your_token_here"
    exit 1
fi

# Install the Doppler Kubernetes Operator if not already installed
echo "Checking if Doppler Operator is installed..."
if ! kubectl get crd dopplersecrets.secrets.doppler.com &> /dev/null; then
    echo "Installing Doppler Kubernetes Operator..."
    kubectl apply -f https://github.com/DopplerHQ/kubernetes-operator/releases/latest/download/doppler-operator.yaml
else
    echo "Doppler Operator is already installed."
fi

# Create the atheon namespace if it doesn't exist
echo "Creating atheon namespace if it doesn't exist..."
kubectl create namespace atheon --dry-run=client -o yaml | kubectl apply -f -

# Deploy the Doppler Secret resources
echo "Deploying Doppler Secret resources..."
envsubst < infra/kubernetes/doppler-operator.yaml | kubectl apply -f -

echo "Verifying deployment..."
kubectl get dopplersecret -n atheon
kubectl get secret doppler-token-secret -n atheon

echo "Doppler deployment complete!"
echo "You can now deploy the Atheon AI services."