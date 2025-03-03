# Atheon AI

Atheon AI is an advanced orchestration platform that manages AI agents and human-in-the-loop workflows. The system delegates tasks to specialized horizontal agents while maintaining human oversight for critical decisions.

## Features

- **Task Orchestration**: Efficiently route tasks to specialized AI agents
- **Human-in-the-Loop (HITL)**: Maintain human oversight for critical decisions
- **Specialized Agents**: Dedicated agents for summarization, web scraping, transcription, and more
- **Kafka Integration**: Reliable message passing between components
- **Modern Frontend**: React + Next.js frontend with Tailwind CSS and shadcn/ui
- **Containerized Architecture**: Docker and Kubernetes ready

## Project Structure

```
atheon-ai/
├── backend/
│   ├── agents/           # Horizontal agents for specific tasks
│   ├── kafka/            # Kafka producers and consumers
│   └── orchestrator/     # Vertical agent for task orchestration
├── database/             # Database schema and migrations
├── frontend/             # Next.js frontend application
└── infra/                # Infrastructure configuration
    ├── argocd/           # ArgoCD application configuration
    ├── ci-cd/            # GitHub Actions workflow
    └── kubernetes/       # Kubernetes deployment configurations
```

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