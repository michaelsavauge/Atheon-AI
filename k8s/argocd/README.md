# Atheon AI ArgoCD Configuration

This directory contains the ArgoCD configuration for the Atheon AI multi-agent orchestration system. ArgoCD is used for GitOps-based continuous delivery of the Kubernetes resources.

## Files

- `atheon-ai-project.yaml`: Defines the ArgoCD project for Atheon AI, including permissions and resource constraints
- `atheon-ai-appset.yaml`: ApplicationSet that generates applications for all services across all environments
- `orchestrator-app.yaml`: Example standalone application for the orchestrator service (can be used as a template)

## Setup

### Prerequisites

- Kubernetes cluster with ArgoCD installed
- `kubectl` configured to access the cluster
- ArgoCD CLI installed (optional)

### Installation

1. Apply the project configuration:

```bash
kubectl apply -f k8s/argocd/atheon-ai-project.yaml
```

2. Apply the ApplicationSet:

```bash
kubectl apply -f k8s/argocd/atheon-ai-appset.yaml
```

This will automatically create applications for all services across all environments.

## Usage

### Accessing the ArgoCD UI

Access the ArgoCD UI to view the status of your applications:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Then open https://localhost:8080 in your browser.

### Syncing Applications

Applications will automatically sync based on the configuration in the ApplicationSet. You can also manually sync applications from the ArgoCD UI or using the CLI:

```bash
argocd app sync orchestrator-production
```

### Adding a New Service

To add a new service:

1. Add the service to the list in `atheon-ai-appset.yaml`
2. Apply the updated ApplicationSet:

```bash
kubectl apply -f k8s/argocd/atheon-ai-appset.yaml
```

## Environments

The ApplicationSet creates applications for three environments:

- **Development**: Used for active development and testing
- **Staging**: Used for pre-production validation
- **Production**: Used for the live system

Each environment uses its corresponding Kustomize overlay from the `k8s/overlays` directory.

## Security

The ArgoCD project configuration includes:

- Restricted source repositories
- Namespace restrictions
- Resource whitelisting
- Role-based access control

## Troubleshooting

Common issues and solutions:

1. **Application not syncing**: Check the sync status and logs in the ArgoCD UI
2. **Resource conflicts**: Ensure that resources are not being managed by multiple applications
3. **Permission issues**: Verify that the ArgoCD service account has the necessary permissions

For more detailed troubleshooting, check the ArgoCD logs:

```bash
kubectl logs -f deployment/argocd-application-controller -n argocd
``` 