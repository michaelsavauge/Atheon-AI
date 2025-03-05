# Contributing to Atheon AI

Thank you for your interest in contributing to Atheon AI! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful, inclusive, and considerate in all interactions.

## Development Process

### Branch Strategy

- `main`: The primary branch that contains the latest stable code
- `develop`: Integration branch for features before they are merged to `main`
- `feature/*`: Feature branches for new functionality
- `bugfix/*`: Branches for bug fixes
- `release/*`: Release preparation branches
- `hotfix/*`: Emergency fixes for production issues

### Pull Request Process

1. Fork the repository and create your branch from `develop`
2. Make your changes, following the coding standards
3. Add or update tests as necessary
4. Update documentation to reflect any changes
5. Submit a pull request to the `develop` branch
6. Ensure all CI checks pass
7. Wait for review and address any feedback

## Coding Standards

### General Guidelines

- Follow the established code style for each language
- Write clear, descriptive commit messages
- Keep pull requests focused on a single change
- Include appropriate tests for new functionality
- Document new code using standard documentation formats

### Python Guidelines

- Use type hints for all functions
- Follow PEP 8 style guidelines
- Use docstrings for all public functions and classes
- Organize imports alphabetically
- Use `poetry` for dependency management

### TypeScript/JavaScript Guidelines

- Use TypeScript for all new code
- Follow the project's ESLint and Prettier configurations
- Use functional components with hooks for React
- Use absolute imports instead of relative imports
- Document complex functions and components

### Go Guidelines

- Follow standard Go formatting (use `gofmt`)
- Use error handling with appropriate context
- Document exported functions and types
- Use concurrency patterns appropriately
- Follow the project's established package structure

### Rust Guidelines

- Follow Rust's official style guidelines
- Use proper error handling with `Result` types
- Document public functions and types
- Use memory-safe practices
- Follow the project's established module structure

## Testing

- Write unit tests for all new functionality
- Ensure tests are isolated and don't depend on external services
- Mock external dependencies when necessary
- Aim for high test coverage, especially for critical paths
- Include integration tests for API endpoints

## Documentation

- Update README.md with any necessary changes
- Document new features in the appropriate documentation files
- Include code examples where helpful
- Keep API documentation up-to-date
- Document configuration options and environment variables

## Submitting Issues

When submitting an issue, please include:

- A clear, descriptive title
- A detailed description of the problem
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Screenshots or logs if applicable
- Environment information (OS, browser, etc.)

## Getting Help

If you need help with your contribution, you can:

- Ask questions in the issue you're working on
- Join our community chat
- Reach out to the maintainers directly

Thank you for contributing to Atheon AI! 