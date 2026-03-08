# Microservices Project

A collection of Go microservices for authentication, user management, and transaction processing.

## Project Structure

```
├── services/
│   ├── auth-service/         # Authentication service
│   ├── user-service/         # User management service
│   └── transaction-service/  # Transaction processing service
├── shared/                   # Shared libraries and utilities
│   ├── auth/                 # JWT utilities and claims
│   ├── logging/              # Zap logger configuration
│   ├── telemetry/            # OpenTelemetry setup
│   └── proto/                # Protocol buffers (gRPC)
└── .github/workflows/        # CI/CD workflows
```

## Getting Started

### Prerequisites

- Go 1.22 or higher
- Docker (for containerization)
- Make

### Building the Services

```bash
# Build all services
make build

# Build Docker images
make docker-build
```

### Running Tests

```bash
make test
```

### Linting

```bash
make lint
```

## Services

### Auth Service
Handles authentication and authorization.

### User Service
Manages user profiles and information.

### Transaction Service
Processes transactions and emits events.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
