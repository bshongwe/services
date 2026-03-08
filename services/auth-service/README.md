# Auth Service

Authentication microservice providing user registration and login with JWT token generation.

## Features

- ✅ User registration with secure password hashing (bcrypt)
- ✅ User login with JWT token issuance
- ✅ PostgreSQL database integration with GORM
- ✅ Input validation
- ✅ Proper error handling
- ✅ Health check endpoint

## Architecture

```
internal/
├── handler/       # HTTP request handlers
├── service/       # Business logic layer
├── repository/    # Data access layer
├── model/         # Domain models
└── database/      # Database configuration
```

## API Endpoints

### Health Check
```
GET /health
Response: {"status": "healthy"}
```

### Register User
```
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response 201:
{
  "message": "User registered successfully",
  "user_id": "uuid",
  "email": "user@example.com"
}
```

### Login
```
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response 200:
{
  "message": "Login successful",
  "token": "jwt.token.here"
}
```

## Environment Variables

```bash
DB_HOST=localhost          # Database host
DB_PORT=5432              # Database port
DB_USER=postgres          # Database user
DB_PASSWORD=postgres      # Database password
DB_NAME=auth_db           # Database name
DB_SSLMODE=disable        # SSL mode (disable, require, verify-full)
JWT_SECRET=your-secret    # JWT signing secret
PORT=8080                 # Service port
```

## Running Locally

### Prerequisites
- Go 1.22+
- PostgreSQL 14+
- Docker & Docker Compose (optional)

### Quick Start with Docker Compose (Recommended)

```bash
# Start the service and database
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

The service will be available at `http://localhost:8080`

### Manual Setup

1. Install dependencies:
```bash
go mod download
```

2. Create database:
```bash
createdb auth_db
```

3. Set environment variables:
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=auth_db
export JWT_SECRET=your-super-secret-key
```

4. Run the service:
```bash
go run cmd/server/main.go
# Or use the Makefile
make run
```

## Testing

```bash
# Run tests
go test ./...

# Run tests with coverage
go test -cover ./...

# Test registration
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Test login
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

## Security Features

- **Password Hashing**: Uses bcrypt with default cost factor (10)
- **JWT Tokens**: HS256 signing algorithm with 24-hour expiration
- **Input Validation**: Email format and minimum password length (8 chars)
- **SQL Injection Prevention**: Parameterized queries via GORM

## Future Enhancements

- [ ] Refresh token mechanism
- [ ] Email verification
- [ ] Password reset flow
- [ ] Rate limiting
- [ ] OAuth2 integration
- [ ] Multi-factor authentication
- [ ] Audit logging
