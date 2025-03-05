# Atheon AI Kubernetes Configuration

This directory contains the Kubernetes configuration for the Atheon AI multi-agent orchestration system. The configuration is organized using Kustomize to manage different environments.

## Directory Structure

```
k8s/
├── base/                   # Base configuration shared across all environments
│   ├── configmaps/         # ConfigMaps for application configuration
│   ├── deployments/        # Deployment configurations for all services
│   ├── network-policies/   # Network policies for zero-trust security
│   ├── secrets/            # Secret placeholders (actual secrets managed by Doppler)
│   ├── services/           # Service configurations for all components
│   └── kustomization.yaml  # Base kustomization file
├── overlays/               # Environment-specific overlays
│   ├── development/        # Development environment configuration
│   │   ├── patches/        # Patches specific to development
│   │   └── kustomization.yaml
│   ├── staging/            # Staging environment configuration
│   │   ├── patches/        # Patches specific to staging
│   │   └── kustomization.yaml
│   └── production/         # Production environment configuration
│       ├── patches/        # Patches specific to production
│       └── kustomization.yaml
└── README.md               # This file
```

## Components

The Atheon AI system consists of the following components:

1. **Orchestrator**: Central service that manages task routing and delegation
2. **Scraper**: Go-based web scraping agent
3. **Data Fetcher**: Rust-based API data fetching agent
4. **Summarizer**: Python-based text summarization agent
5. **Frontend**: Next.js web interface
6. **Infrastructure**: PostgreSQL, Redis, Kafka (configured separately)

## Environment Configuration

### Development

The development environment is configured with:
- Single replica for each service
- Reduced resource limits
- Debug logging enabled
- Latest container images

### Staging

The staging environment is configured with:
- Two replicas for each service
- Moderate resource limits
- Standard logging
- Staging-tagged container images

### Production

The production environment is configured with:
- Higher replica counts (3-5 per service)
- Horizontal Pod Autoscalers (HPA) for automatic scaling
- Pod Disruption Budgets (PDB) for high availability
- Higher resource limits
- Release-versioned container images

## Deployment

### Prerequisites

- Kubernetes cluster (EKS, GKE, AKS, or local)
- kubectl installed and configured
- kustomize installed (v4.0.0+)
- Doppler CLI for secrets management

### Deploying to an Environment

1. Set up Doppler secrets:

```bash
doppler setup --project atheon-ai --config [environment]
```

2. Deploy using kustomize:

```bash
# For development
kubectl apply -k k8s/overlays/development

# For staging
kubectl apply -k k8s/overlays/staging

# For production
kubectl apply -k k8s/overlays/production
```

### Customizing Deployment

To customize the deployment for a specific environment, modify the corresponding files in the appropriate overlay directory.

## Security

The configuration implements a zero-trust security model with:
- Default deny-all network policy
- Specific network policies for each component
- Non-root container execution
- Resource limits to prevent DoS
- Secrets management via Doppler

## Monitoring

All services expose Prometheus metrics endpoints for monitoring:
- Orchestrator: `/metrics` on port 8081
- Scraper: `/metrics` on port 8083
- Data Fetcher: `/metrics` on port 8085
- Summarizer: `/metrics` on port 8087
- Frontend: `/api/metrics` on port 3000

## Maintenance

### Updating Configurations

1. Modify the base configuration if the change applies to all environments
2. Modify the overlay if the change is environment-specific
3. Test changes in development before promoting to staging and production

### Scaling

- In development and staging, modify the `replicas-patch.yaml` file
- In production, the HPA will automatically scale based on CPU and memory utilization

## Troubleshooting

Common issues and solutions:

1. **Pod fails to start**: Check events with `kubectl describe pod [pod-name]`
2. **Service unavailable**: Verify network policies allow the required traffic
3. **Resource constraints**: Check if pods are being throttled due to resource limits

For more detailed troubleshooting, check the logs:

```bash
kubectl logs -f deployment/[deployment-name] -n atheon-ai-[environment]
``` 