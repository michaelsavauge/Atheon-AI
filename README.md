# Atheon AI - Multi-Agent Orchestration System

Atheon AI is a sophisticated multi-agent orchestration system designed to efficiently manage and coordinate various AI agents for tasks such as web scraping, data fetching, summarization, and transcription. The system leverages a vertical orchestration approach with horizontal task execution, enabling complex workflows with human-in-the-loop validation.

## System Architecture

![Atheon AI Architecture](docs/architecture.png)

The system consists of the following components:

### Backend Services

- **Orchestrator**: Central service built with Python, FastAPI, and LangGraph that manages task routing and delegation
- **Scraper Agent**: Go-based web scraping service using Colly framework for concurrent operations
- **Data Fetcher Agent**: Rust-based API data fetching service using Tokio for asynchronous processing
- **Summarizer Agent**: Python-based text summarization service using LLMs
- **Transcription Agent**: Python-based speech-to-text service using Whisper

### Frontend

- **Web Interface**: Next.js application with Tailwind CSS and Shadcn UI components

### Infrastructure

- **Message Broker**: Kafka for asynchronous communication between services
- **Database**: PostgreSQL for persistent storage
- **Cache**: Redis for temporary data and rate limiting
- **Observability**: Prometheus, Grafana, and Jaeger for monitoring and tracing

## Repository Structure

```
atheon-ai/
├── backend/
│   ├── orchestrator/           # Python-based orchestration service
│   │   ├── src/                # Source code
│   │   ├── tests/              # Unit and integration tests
│   │   └── Dockerfile          # Container definition
│   ├── agents/
│       ├── python_agent_template/  # Template for Python agents
│       ├── go_agent_template/      # Template for Go agents
│       └── rust_agent_template/    # Template for Rust agents
├── frontend/                   # Next.js web interface
│   ├── src/                    # Source code
│   ├── public/                 # Static assets
│   └── Dockerfile              # Container definition
├── k8s/                        # Kubernetes configuration
│   ├── base/                   # Base Kustomize configuration
│   ├── overlays/               # Environment-specific overlays
│   └── argocd/                 # ArgoCD configuration
├── .github/                    # GitHub Actions workflows
│   └── workflows/              # CI/CD pipeline definitions
└── docker-compose.yml          # Local development setup
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Kubernetes cluster (for production deployment)
- kubectl and kustomize
- Doppler CLI (for secrets management)

### Local Development

1. Clone the repository:

```bash
git clone https://github.com/your-org/atheon-ai.git
cd atheon-ai
```

2. Set up environment variables with Doppler:

```bash
doppler setup --project atheon-ai --config dev
```

3. Start the development environment:

```bash
docker-compose up -d
```

4. Access the services:
   - Frontend: http://localhost:3000
   - Orchestrator API: http://localhost:8080
   - Kafka UI: http://localhost:8090

### Deployment

The system can be deployed to Kubernetes using Kustomize and ArgoCD:

```bash
# Deploy to development
kubectl apply -k k8s/overlays/development

# Deploy to staging
kubectl apply -k k8s/overlays/staging

# Deploy to production
kubectl apply -k k8s/overlays/production
```

For more details, see the [Kubernetes README](k8s/README.md) and [ArgoCD README](k8s/argocd/README.md).

## Development Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run tests locally
4. Submit a pull request
5. After approval and CI checks pass, merge to `main`
6. Automated deployment to development environment
7. Manual promotion to staging and production

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 