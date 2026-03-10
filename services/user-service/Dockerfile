# User Service Dockerfile
# Build from services/ directory: docker build -f user-service/Dockerfile -t user-service .
FROM golang:1.23-alpine AS builder

WORKDIR /build

# Copy go modules
COPY user-service/go.mod user-service/go.sum ./user-service/

# Download dependencies
WORKDIR /build/user-service
RUN go mod download

# Copy source code
WORKDIR /build
COPY user-service/ ./user-service/

# Build the binary
WORKDIR /build/user-service
RUN CGO_ENABLED=0 GOOS=linux go build -o user-service ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /build/user-service/user-service .

EXPOSE 8080

CMD ["./user-service"]
