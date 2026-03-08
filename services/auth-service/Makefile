.PHONY: help build run test lint clean docker-build docker-run migrate

help: ## Display this help message
	@echo "Auth Service - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

build: ## Build the auth service binary
	@echo "Building auth-service..."
	go build -o ../../bin/auth-service ./cmd/server

run: ## Run the auth service locally
	@echo "Running auth-service..."
	go run cmd/server/main.go

test: ## Run all tests
	@echo "Running tests..."
	go test -v ./...

test-cover: ## Run tests with coverage
	@echo "Running tests with coverage..."
	go test -cover -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

lint: ## Run linter
	@echo "Running linter..."
	go vet ./...
	go fmt ./...

clean: ## Clean build artifacts
	@echo "Cleaning..."
	rm -f ../../bin/auth-service
	rm -f coverage.out coverage.html

deps: ## Download dependencies
	@echo "Downloading dependencies..."
	go mod download
	go mod tidy

docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t auth-service:latest .

docker-run: ## Run service in Docker
	@echo "Running Docker container..."
	docker run -p 8080:8080 \
		-e DB_HOST=host.docker.internal \
		-e DB_PORT=5432 \
		-e DB_USER=postgres \
		-e DB_PASSWORD=postgres \
		-e DB_NAME=auth_db \
		-e JWT_SECRET=your-secret \
		auth-service:latest

db-create: ## Create the database
	@echo "Creating database..."
	createdb auth_db || echo "Database might already exist"

db-drop: ## Drop the database
	@echo "Dropping database..."
	dropdb auth_db || echo "Database might not exist"

migrate: ## Run database migrations
	@echo "Running migrations..."
	go run cmd/server/main.go &
	@sleep 2
	@pkill -f "go run cmd/server/main.go" || true

dev: ## Run in development mode with auto-reload
	@echo "Starting development mode..."
	@which air > /dev/null || go install github.com/cosmtrek/air@latest
	air
