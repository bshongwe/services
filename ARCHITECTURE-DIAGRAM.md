# System Architecture - How Logging Fits

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MICROSERVICES LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  auth-service   │  │  user-service   │  │ transaction-svc │  │
│  │                 │  │                 │  │                 │  │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │  │
│  │  │ Handler   │  │  │  │ Handler   │  │  │  │ Handler   │  │  │
│  │  │   ↓       │  │  │  │   ↓       │  │  │  │   ↓       │  │  │
│  │  │ Service   │  │  │  │ Service   │  │  │  │ Service   │  │  │
│  │  │   ↓       │  │  │  │   ↓       │  │  │  │   ↓       │  │  │
│  │  │Repository │  │  │  │Repository │  │  │  │Repository │  │  │
│  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │  │
│  │        ↓        │  │        ↓        │  │        ↓        │  │
│  └────────┼────────┘  └────────┼────────┘  └────────┼────────┘  │
│           ↓                    ↓                     ↓           │
└───────────┼────────────────────┼─────────────────────┼───────────┘
            │                    │                     │
            └────────────────────┼─────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      SHARED LIBRARIES LAYER                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │   logging    │  │     auth     │  │    config    │            │
│  │              │  │              │  │              │            │
│  │ NewProduction│  │ JWTManager   │  │ LoadWithDefs │            │
│  │ NewDevelopment│  │ Generate()   │  │ GetString()  │            │
│  │ WithFields() │  │ Verify()     │  │ GetInt()     │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐                               │
│  │  telemetry   │  │    proto/    │                               │
│  │              │  │              │                               │
│  │ InitTracer() │  │ (gRPC defs)  │                               │
│  │ StartSpan()  │  │              │                               │
│  └──────────────┘  └──────────────┘                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL DEPENDENCIES                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │   Zap    │  │   Viper  │  │   JWT    │  │   GORM   │          │
│  │ (logging)│  │ (config) │  │  (auth)  │  │   (DB)   │          │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                         │
│  │   Gin    │  │ OpenTel  │  │PostgreSQL│                         │
│  │  (HTTP)  │  │ (tracing)│  │   (DB)   │                         │
│  └──────────┘  └──────────┘  └──────────┘                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Example: User Registration with Logging

```
1. HTTP Request
      ↓
2. Handler (auth.go)
      │
      ├─→ logger.Info("Registration attempt", zap.String("email", email))
      ↓
3. Service (auth_service.go)
      │
      ├─→ logger.Debug("Hashing password")
      ↓
4. Repository (user_repository.go)
      │
      ├─→ logger.Debug("Creating user in database")
      ↓
5. Database (PostgreSQL)
      │
      ↓
6. Repository returns
      │
      ├─→ logger.Info("User created successfully", zap.String("user_id", id))
      ↓
7. Service returns
      ↓
8. Handler returns
      │
      ├─→ logger.Info("Registration completed", zap.Duration("duration", d))
      ↓
9. HTTP Response
```

## Logging Integration Points

### ✅ **Currently Integrated:**

1. **auth-service/main.go**
   ```go
   logger, _ := logging.NewProduction()
   logger.Info("Starting Auth Service")
   ```

2. **Database initialization**
   ```go
   logger.Info("Database migrations completed successfully")
   ```

3. **Error handling**
   ```go
   if err != nil {
       log.Fatalf("Failed to connect: %v", err)
   }
   ```

### 🔜 **Ready to Integrate:**

1. **user-service** - Same pattern as auth-service
2. **transaction-service** - Plus event logging
3. **HTTP middleware** - Request/response logging
4. **gRPC interceptors** - RPC call logging
5. **Background workers** - Job processing logs

## Configuration Flow

```
Environment Variables
      ↓
shared/config → Load settings
      ↓
shared/logging → Configure logger based on ENV
      ↓
Services → Use configured logger
      ↓
Outputs (stdout/stderr in JSON or console format)
```

## Go Workspace Structure

```
go.work
   ├─→ services/auth-service       (imports shared/logging)
   ├─→ services/user-service       (imports shared/logging)
   ├─→ services/transaction-service(imports shared/logging)
   ├─→ shared/logging              ← YOU ARE HERE
   ├─→ shared/auth                 (may log JWT operations)
   ├─→ shared/config              (no logging dependency)
   └─→ shared/telemetry           (may log tracing info)
```

## Dependency Graph

```
┌─────────────────────────────────────┐
│         auth-service                │
│         user-service                │
│         transaction-service         │
└─────────────────┬───────────────────┘
                  │ depends on
                  ↓
┌─────────────────────────────────────┐
│         shared/logging              │ ← Simple, no deps on other shared
└─────────────────┬───────────────────┘
                  │ depends on
                  ↓
┌─────────────────────────────────────┐
│         go.uber.org/zap             │
└─────────────────────────────────────┘

✅ Clean dependency tree!
✅ No circular dependencies!
✅ Easy to test!
```

## CI/CD Pipeline Integration

```
GitHub Actions
      ↓
1. Checkout code
      ↓
2. Set up Go 1.23
      ↓
3. Run: go test ./...
      │
      ├─→ shared/logging tests pass ✅
      ├─→ auth-service tests (use logging) pass ✅
      ↓
4. Build Docker images
      │
      ├─→ Logging included in all images ✅
      ↓
5. Deploy to environment
      │
      ENV=production → JSON logs to stdout ✅
      ENV=development → Pretty logs to console ✅
```

## Production Deployment Example

```
Kubernetes Pod (auth-service)
      ↓
Container starts
      ↓
ENV=production is set
      ↓
logging.NewProduction() called
      ↓
JSON structured logs to stdout
      ↓
Kubernetes captures logs
      ↓
Forwarded to logging aggregator (ELK/Loki/CloudWatch)
      ↓
Queryable, searchable, alertable ✅
```

## Summary: Why This Aligns Perfectly

```
✅ Layered Architecture     → Logging is in shared layer
✅ Dependency Injection     → Logger injected at startup
✅ Clean Dependencies       → No circular deps
✅ 12-Factor App           → Config from environment
✅ Microservices Ready     → Each service logs independently
✅ Cloud Native            → JSON logs, no state
✅ Developer Experience    → Pretty logs in dev mode
✅ Production Ready        → Structured JSON in prod
✅ Observable              → Ready for tracing integration
✅ Testable                → Simple mocking
```

**Everything fits together perfectly!** 🎉
