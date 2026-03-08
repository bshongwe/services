.PHONY: help build test lint clean docker-build

help: ## Display this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

build: ## Build all services
	@echo "Building auth-service..."
	cd services/auth-service && go build -o ../../bin/auth-service ./cmd/server
	@echo "Building user-service..."
	cd services/user-service && go build -o ../../bin/user-service ./cmd/server
	@echo "Building transaction-service..."
	cd services/transaction-service && go build -o ../../bin/transaction-service ./cmd/server

test: ## Run tests for all services
	@echo "Running tests..."
	cd services/auth-service && go test ./...
	cd services/user-service && go test ./...
	cd services/transaction-service && go test ./...

lint: ## Run linter for all services
	@echo "Running linter..."
	cd services/auth-service && go vet ./...
	cd services/user-service && go vet ./...
	cd services/transaction-service && go vet ./...

clean: ## Clean build artifacts
	@echo "Cleaning..."
	rm -rf bin/

docker-build: ## Build Docker images for all services
	@echo "Building Docker images..."
	docker build -t auth-service:latest ./services/auth-service
	docker build -t user-service:latest ./services/user-service
	docker build -t transaction-service:latest ./services/transaction-service
