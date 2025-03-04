# Atheon AI Platform

Atheon AI is an advanced AI agent orchestration system that handles task orchestration, human-in-the-loop workflows, and specialized horizontal agents for various tasks.

## Features

- **Task Orchestration**: Efficiently route tasks to specialized AI agents
- **Human-in-the-Loop (HITL)**: Maintain human oversight for critical decisions
- **Specialized Agents**: Dedicated agents for summarization, web scraping, transcription, and more
- **Kafka Integration**: Reliable message passing between components
- **Modern Frontend**: React + Next.js frontend with Tailwind CSS and shadcn/ui
- **Containerized Architecture**: Docker and Kubernetes ready

## Project Structure

The platform consists of:

- **Backend**
  - Orchestrator (Python/FastAPI) - The vertical agent that routes tasks
  - Scraper Agent (Go) - Web scraping service
  - Data Fetcher Agent (Rust) - API data retrieval service
  - Kafka - Message queue for agent communication
  - PostgreSQL - Main database
  - Redis - Caching and session management

- **Frontend**
  - Next.js/React application with Tailwind CSS and Shadcn/ui

## Prerequisites

- Docker and Docker Compose
- Doppler CLI for secrets management
- kubectl and kustomize for Kubernetes deployment
- Node.js/npm for frontend development

## Secrets Management with Doppler

This project uses [Doppler](https://www.doppler.com/) for secrets management. **No secrets should be hardcoded or stored in .env files.**

### Setting up Doppler

1. **Install Doppler CLI**:
   ```bash
   # macOS
   brew install dopplerhq/cli/doppler
   
   # Ubuntu/Debian
   curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | sudo apt-key add -
   echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/doppler-cli.list
   sudo apt-get update && sudo apt-get install -y doppler
   ```

2. **Login and setup project**:
   ```bash
   doppler login
   doppler setup --project atheon-ai --config dev
   ```

3. **Use Doppler with Docker Compose**:
   ```bash
   doppler run -- docker-compose up -d
   ```

4. **Use Doppler with Kubernetes**:
   ```bash
   doppler run -- kubectl apply -k k8s/overlays/dev
   ```

### Required Secrets

The following secrets are required in your Doppler project:

| Category | Secret Name | Description |
|----------|-------------|-------------|
| **Database** | `DATABASE_URL` | PostgreSQL connection string |
| | `POSTGRES_USER` | Database username |
| | `POSTGRES_PASSWORD` | Database password |
| | `POSTGRES_DB` | Database name |
| **Authentication** | `JWT_SECRET_KEY` | JWT signing key |
| | `JWT_ALGORITHM` | Algorithm for JWT (e.g., HS256) |
| | `JWT_REFRESH_SECRET` | Refresh token secret |
| **LLM APIs** | `OPENAI_API_KEY` | OpenAI API key |
| | `ANTHROPIC_API_KEY` | Anthropic API key |
| | `HUGGINGFACE_API_KEY` | HuggingFace API key |
| | `HUMANLAYER_API_KEY` | HumanLayer API key |
| | `HUMANLAYER_PROJECT_ID` | HumanLayer project ID |
| **Kafka** | `KAFKA_USERNAME` | Kafka username |
| | `KAFKA_PASSWORD` | Kafka password |
| | `KAFKA_SSL_CERT` | Kafka SSL certificate |
| | `KAFKA_SSL_KEY` | Kafka SSL key |
| **Monitoring** | `OPENTELEMETRY_API_KEY` | OpenTelemetry API key |
| | `GRAFANA_API_KEY` | Grafana API key |
| **AWS** | `AWS_ACCESS_KEY_ID` | AWS access key |
| | `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| | `AWS_REGION` | AWS region |
| | `AWS_S3_BUCKET` | S3 bucket name |
| **Other** | `LOG_LEVEL` | Logging level |

## Local Development

### Running Backend Services

```bash
# Create and update the doppler.yaml file if needed
./scripts/run-backend.sh
```

### Building and Running Frontend

```bash
# First build the frontend container
./scripts/build-frontend.sh

# Then run it with Doppler
doppler run -- docker-compose up -d frontend
```

### Running Everything Together

```bash
doppler run -- docker-compose up -d
```

## Kubernetes Deployment

We use Kustomize for managing Kubernetes manifests with environment overlays:

```bash
# Development
doppler run --config=dev -- kubectl apply -k k8s/overlays/dev

# Production
doppler run --config=prod -- kubectl apply -k k8s/overlays/prod
```

## Development Workflow

1. Use `poetry` for Python dependency management
2. All code must pass type checking and linting
3. Follow the project conventions in [project-rules.mdc](docs/project-rules.mdc)
4. Use Doppler for managing all secrets and configuration

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+
- Python 3.10+
- Poetry (Python package manager)
- Doppler CLI (for secrets management)

### Local Development

1. Clone the repository:

```bash
git clone https://github.com/atheon-ai/atheon-ai.git
cd atheon-ai
```

2. Set up Doppler for secrets management:

```bash
# Install Doppler CLI (macOS)
brew install dopplerhq/cli/doppler

# Login to Doppler
doppler login

# Set up project configuration
doppler setup --project atheon-ai --config dev
```

3. Start the development environment with Doppler:

```bash
# Using the helper script
./scripts/doppler-run.sh docker-compose up -d

# Or directly with Doppler
doppler run -- docker-compose up -d
```

4. Access the services:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Adminer (DB UI): http://localhost:8080
   - Kafka UI: http://localhost:8081

### Development Workflow

1. Backend development:
   - The orchestrator service is located in `backend/orchestrator/`
   - Make changes to the code and the service will automatically reload

2. Frontend development:
   - The frontend is located in `frontend/`
   - Make changes to the code and the service will automatically reload

## Deployment

See the [Infrastructure README](infra/README.md) for detailed deployment instructions.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 