# Transaction Service Dockerfile
# Build from repo root: docker build -f services/transaction-service/Dockerfile -t transaction-service .
FROM golang:1.23-alpine AS builder

WORKDIR /build

# Copy go modules
COPY services/transaction-service/go.mod services/transaction-service/go.sum ./services/transaction-service/

# Download dependencies
WORKDIR /build/services/transaction-service
RUN go mod download

# Copy source code
WORKDIR /build
COPY services/transaction-service/ ./services/transaction-service/

# Build the binary
WORKDIR /build/services/transaction-service
RUN CGO_ENABLED=0 GOOS=linux go build -o transaction-service ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /build/services/transaction-service/transaction-service .

EXPOSE 8080

CMD ["./transaction-service"]
