.PHONY: help build test lint clean docker-build build-auth build-user build-transaction test-auth test-user test-transaction docker-auth docker-user docker-transaction

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
	@echo "✅ All services built successfully"

test: ## Run tests for all services with verbose output
	@echo "Running tests..."
	cd services/auth-service && go test ./... -v
	cd services/user-service && go test ./... -v
	cd services/transaction-service && go test ./... -v
	@echo "✅ All tests completed"

lint: ## Run linter for all services (go vet + staticcheck)
	@echo "Running linter..."
	cd services/auth-service && go vet ./... && staticcheck ./...
	cd services/user-service && go vet ./... && staticcheck ./...
	cd services/transaction-service && go vet ./... && staticcheck ./...
	@echo "✅ Linting completed"

clean: ## Clean build artifacts
	@echo "Cleaning..."
	rm -rf bin/
	@echo "✅ Cleaned"

docker-build: ## Build Docker images for all services
	@echo "Building Docker images..."
	docker build -t auth-service:latest ./services/auth-service
	docker build -t user-service:latest ./services/user-service
	docker build -t transaction-service:latest ./services/transaction-service
	@echo "✅ All Docker images built"

# Individual service commands (for development)
build-auth: ## Build only auth-service
	@echo "Building auth-service..."
	cd services/auth-service && go build -o ../../bin/auth-service ./cmd/server
	@echo "✅ auth-service built"

build-user: ## Build only user-service
	@echo "Building user-service..."
	cd services/user-service && go build -o ../../bin/user-service ./cmd/server
	@echo "✅ user-service built"

build-transaction: ## Build only transaction-service
	@echo "Building transaction-service..."
	cd services/transaction-service && go build -o ../../bin/transaction-service ./cmd/server
	@echo "✅ transaction-service built"

test-auth: ## Test only auth-service
	@echo "Testing auth-service..."
	cd services/auth-service && go test ./... -v

test-user: ## Test only user-service
	@echo "Testing user-service..."
	cd services/user-service && go test ./... -v

test-transaction: ## Test only transaction-service
	@echo "Testing transaction-service..."
	cd services/transaction-service && go test ./... -v

docker-auth: ## Build Docker image for auth-service only
	@echo "Building Docker image for auth-service..."
	docker build -t auth-service:latest ./services/auth-service
	@echo "✅ auth-service image built"

docker-user: ## Build Docker image for user-service only
	@echo "Building Docker image for user-service..."
	docker build -t user-service:latest ./services/user-service
	@echo "✅ user-service image built"

docker-transaction: ## Build Docker image for transaction-service only
	@echo "Building Docker image for transaction-service..."
	docker build -t transaction-service:latest ./services/transaction-service
	@echo "✅ transaction-service image built"
