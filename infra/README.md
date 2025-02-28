# Atheon AI Infrastructure

This directory contains all the infrastructure configuration files for the Atheon AI project.

## Directory Structure

- `argocd/`: ArgoCD application configuration
- `ci-cd/`: GitHub Actions workflow configuration
- `kubernetes/`: Kubernetes deployment configurations

## Local Development

For local development, use the Docker Compose configuration in the root directory:

```bash
docker-compose up -d
```

This will start all the necessary services:
- Orchestrator (FastAPI backend)
- Frontend (Next.js)
- PostgreSQL database
- Kafka message broker
- Adminer (database management UI)
- Kafka UI (Kafka management UI)

## Kubernetes Deployment

The Kubernetes deployment is managed through ArgoCD. The application configuration is defined in `argocd/application.yaml`.

### Prerequisites

- Kubernetes cluster
- ArgoCD installed in the cluster
- Doppler for secrets management

### Deployment Steps

1. Create the necessary secrets:

```bash
# Export environment variables
export POSTGRES_PASSWORD=your_secure_password
export JWT_SECRET=your_jwt_secret
export OPENAI_API_KEY=your_openai_api_key
export ANTHROPIC_API_KEY=your_anthropic_api_key
export DOPPLER_TOKEN=your_doppler_token
export GITHUB_USERNAME=your_github_username
export GITHUB_TOKEN=your_github_token
export GITHUB_EMAIL=your_github_email
export GITHUB_AUTH=$(echo -n "${GITHUB_USERNAME}:${GITHUB_TOKEN}" | base64)

# Apply the secrets
envsubst < infra/kubernetes/secrets.yaml | kubectl apply -f -
```

2. Create the ArgoCD application:

```bash
kubectl apply -f infra/argocd/application.yaml
```

3. ArgoCD will automatically sync and deploy all the Kubernetes resources defined in the `infra/kubernetes/` directory.

## CI/CD Pipeline

The CI/CD pipeline is implemented using GitHub Actions. The workflow is defined in `ci-cd/github-actions.yaml`.

The pipeline consists of the following stages:
1. Lint: Check code quality using black, isort, mypy for Python and ESLint for TypeScript
2. Test: Run unit tests for both backend and frontend
3. Build: Build Docker images and push them to GitHub Container Registry
4. Deploy: Sync the ArgoCD application to deploy the latest changes

## Monitoring and Logging

For monitoring and logging, we recommend setting up:
- Prometheus for metrics collection
- Grafana for metrics visualization
- ELK stack (Elasticsearch, Logstash, Kibana) for log aggregation and analysis

These components are not included in the current infrastructure configuration and should be set up separately. 