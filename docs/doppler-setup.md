# Doppler Secrets Management for Atheon AI

This document explains how to set up and use Doppler for secrets management in the Atheon AI project.

## What is Doppler?

Doppler is a universal secrets manager that helps you securely manage and distribute secrets across your applications, environments, and infrastructure. It's used in Atheon AI to manage API keys, database credentials, and other sensitive information.

## Local Development Setup

### 1. Install Doppler CLI

Follow the [official Doppler installation guide](https://docs.doppler.com/docs/install) to install the CLI:

```bash
# macOS
brew install dopplerhq/cli/doppler

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | sudo apt-key add -
echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/doppler-cli.list
sudo apt-get update && sudo apt-get install doppler

# Windows
scoop bucket add doppler https://github.com/DopplerHQ/scoop-doppler.git
scoop install doppler
```

### 2. Login to Doppler

```bash
doppler login
```

### 3. Set Up Project and Environment

```bash
doppler setup --project atheon-ai --config dev
```

## Running Local Development with Doppler

To run any command with Doppler environment variables injected, use:

```bash
./scripts/doppler-run.sh docker-compose up -d
```

This will:
1. Fetch the latest secrets from Doppler
2. Create a temporary `.env` file
3. Start the Docker Compose services with the environment variables

## CI/CD Integration

Doppler is integrated with GitHub Actions for CI/CD:

1. Add your Doppler service token as a GitHub secret named `DOPPLER_TOKEN`
2. The workflow will automatically install Doppler CLI and fetch secrets during the build process

## Kubernetes Integration

For Kubernetes deployments, we use the [Doppler Kubernetes Operator](https://docs.doppler.com/docs/kubernetes-operator):

1. Install the Doppler Operator in your Kubernetes cluster:

```bash
kubectl apply -f https://github.com/DopplerHQ/kubernetes-operator/releases/latest/download/doppler-operator.yaml
```

2. Create a Doppler service token in the Doppler dashboard

3. Deploy the Doppler Secret resources:

```bash
export DOPPLER_SERVICE_TOKEN=dp.st.your_token_here
envsubst < infra/kubernetes/doppler-operator.yaml | kubectl apply -f -
```

## Managing Secrets

### Adding or Updating Secrets

To add or update secrets, use the Doppler dashboard or CLI:

```bash
doppler secrets set API_KEY=value
```

### Viewing Current Secrets

```bash
doppler secrets
```

## Available Environment Variables

See `config/env/.env.example` for a list of all environment variables used in the project.

## Troubleshooting

### Verify Doppler Access

```bash
doppler run -- env | grep DOPPLER
```

### Check if a Secret Exists

```bash
doppler secrets get SOME_SECRET_NAME
```

### Debugging Kubernetes Integration

```bash
kubectl get dopplersecret -n atheon
kubectl get secret doppler-env-vars -n atheon
``` 