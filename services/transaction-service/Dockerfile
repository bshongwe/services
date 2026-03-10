# Transaction Service Dockerfile
# Build from services/ directory: docker build -f transaction-service/Dockerfile -t transaction-service .
FROM golang:1.23-alpine AS builder

WORKDIR /build

# Copy go modules
COPY transaction-service/go.mod transaction-service/go.sum ./transaction-service/

# Download dependencies
WORKDIR /build/transaction-service
RUN go mod download

# Copy source code
WORKDIR /build
COPY transaction-service/ ./transaction-service/

# Build the binary
WORKDIR /build/transaction-service
RUN CGO_ENABLED=0 GOOS=linux go build -o transaction-service ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /build/transaction-service/transaction-service .

EXPOSE 8080

CMD ["./transaction-service"]
