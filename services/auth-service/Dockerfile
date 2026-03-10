# Auth Service Dockerfile
# Build from repo root: docker build -f services/auth-service/Dockerfile -t auth-service .
FROM golang:1.23-alpine AS builder

WORKDIR /build

# Copy go modules for all dependencies
COPY services/auth-service/go.mod services/auth-service/go.sum ./services/auth-service/
COPY shared/logging/go.mod shared/logging/go.sum ./shared/logging/

# Download dependencies
WORKDIR /build/services/auth-service
RUN go mod download

# Copy source code
WORKDIR /build
COPY services/auth-service/ ./services/auth-service/
COPY shared/logging/ ./shared/logging/

# Build the binary
WORKDIR /build/services/auth-service
RUN CGO_ENABLED=0 GOOS=linux go build -o auth-service ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /build/services/auth-service/auth-service .

EXPOSE 8080

CMD ["./auth-service"]
