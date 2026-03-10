# User Service Dockerfile
# Build from repo root: docker build -f services/user-service/Dockerfile -t user-service .
FROM golang:1.23-alpine AS builder

WORKDIR /build

# Copy go modules
COPY services/user-service/go.mod services/user-service/go.sum ./services/user-service/

# Download dependencies
WORKDIR /build/services/user-service
RUN go mod download

# Copy source code
WORKDIR /build
COPY services/user-service/ ./services/user-service/

# Build the binary
WORKDIR /build/services/user-service
RUN CGO_ENABLED=0 GOOS=linux go build -o user-service ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /build/services/user-service/user-service .

EXPOSE 8080

CMD ["./user-service"]
