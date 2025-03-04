# Atheon AI Production Kubernetes Overlay

This directory contains the Kustomize overlay for deploying Atheon AI to a production environment.

## Directory Structure

```
prod/
├── kustomization.yaml       # Main kustomization file
├── patches/                 # Strategic merge patches
│   ├── replicas.yaml        # Sets replica counts for deployments
│   ├── resources.yaml       # Sets resource requests/limits
│   └── hpa.yaml             # Horizontal Pod Autoscaler configurations
└── secrets/                 # Secret files (gitignored)
    ├── atheon-secrets.env   # Atheon service secrets
    └── postgres-secrets.env # Database secrets
```

## Prerequisites

- Kubernetes cluster with version >= 1.22
- kubectl installed and configured
- kustomize installed (v4.x+)
- Doppler CLI installed and configured
- ArgoCD for GitOps deployment (optional)

## Secrets Management with Doppler

This project uses Doppler for managing all secrets. No secrets should be stored in files or hardcoded in configurations.

### Setting up Doppler

1. Install the Doppler CLI:
   ```bash
   # macOS
   brew install dopplerhq/cli/doppler
   
   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
   curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | sudo apt-key add -
   echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/doppler-cli.list
   sudo apt-get update && sudo apt-get install -y doppler
   ```

2. Log in to Doppler:
   ```bash
   doppler login
   ```

3. Configure Doppler with your project:
   ```bash
   doppler setup --project atheon-ai --config prod
   ```

### Deploying with Doppler

Use Doppler to inject secrets when applying Kubernetes configurations:

```bash
doppler run -- kubectl apply -k .
```

Or with ArgoCD:

1. Set up Doppler integration with ArgoCD
2. Configure the ArgoCD Application to use Doppler for secrets:
   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: atheon-ai-prod
     namespace: argocd
   spec:
     project: default
     source:
       repoURL: https://github.com/your-org/atheon-ai.git
       targetRevision: main
       path: k8s/overlays/prod
       plugin:
         name: doppler-secrets
     destination:
       server: https://kubernetes.default.svc
       namespace: atheon-ai
     syncPolicy:
       automated:
         prune: true
         selfHeal: true
   ```

## Required Secrets in Doppler

The following secrets must be configured in your Doppler project:

### Authentication
- JWT_SECRET_KEY
- JWT_ALGORITHM
- JWT_REFRESH_SECRET

### Database
- DATABASE_URL (or individual components)
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_DB

### LLM API Keys
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- HUGGINGFACE_API_KEY

### Monitoring & Logging
- LOG_LEVEL
- OPENTELEMETRY_API_KEY
- GRAFANA_API_KEY

### Kafka
- KAFKA_USERNAME
- KAFKA_PASSWORD
- KAFKA_SSL_CERT
- KAFKA_SSL_KEY

## Deployment

### Using kubectl with kustomize and Doppler

```bash
doppler run -- kubectl apply -k .
```

## Scaling

The production environment is configured with Horizontal Pod Autoscalers (HPAs) that will automatically scale the deployments based on CPU and memory utilization.

- Minimum replicas: 3
- Maximum replicas: 10
- Target CPU utilization: 70%
- Target memory utilization: 80%

## Monitoring

For monitoring the production deployment, use:

```bash
kubectl -n atheon-ai get pods
kubectl -n atheon-ai get hpa
kubectl -n atheon-ai describe deployment orchestrator
```

## Troubleshooting

If you encounter issues with the deployment:

1. Check pod status:
   ```bash
   kubectl -n atheon-ai get pods
   ```

2. Check pod logs:
   ```bash
   kubectl -n atheon-ai logs deployment/orchestrator
   ```

3. Check HPA status:
   ```bash
   kubectl -n atheon-ai describe hpa orchestrator-hpa
   ```

4. Verify Doppler secrets are correctly loaded:
   ```bash
   doppler run -- kubectl get secret -n atheon-ai atheon-secrets -o yaml
   ``` 