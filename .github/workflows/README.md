# GitHub Actions CI/CD - Quick Reference

## 🎯 Workflow Overview

### Trigger Events
- ✅ Push to `main` or `develop` branches
- ✅ Pull requests targeting `main` or `develop`

### Jobs Execution

#### 1️⃣ Build and Test (Runs Always)
- **Parallel Execution**: All 3 services tested simultaneously
- **Duration**: ~2-3 minutes per service
- **Steps**:
  1. Lint code (`go vet`)
  2. Run tests with race detector
  3. Build binary
  4. Upload coverage report

#### 2️⃣ Docker Build (Runs on Main Only)
- **Trigger**: Only when code is pushed to `main`
- **Output**: Docker images with SHA and latest tags
- **Duration**: ~1-2 minutes per service

## 📦 Services Tested

| Service | Path | Binary Output |
|---------|------|---------------|
| Auth Service | `services/auth-service` | `bin/auth-service` |
| User Service | `services/user-service` | `bin/user-service` |
| Transaction Service | `services/transaction-service` | `bin/transaction-service` |

## 🔧 Local Testing (Before Push)

Test your changes locally before pushing:

```bash
# Test a specific service
cd services/auth-service
go vet ./...
go test ./... -v -race
go build -o bin/auth-service ./cmd/server

# Or use the Makefile
make lint test build
```

## 📊 Viewing CI Results

### In GitHub:
1. Go to **Actions** tab in your repository
2. Click on the latest workflow run
3. Expand each job to see detailed logs

### Coverage Reports:
- Uploaded to Codecov (if configured)
- View at: `https://codecov.io/gh/bshongwe/services`

## ⚡ Performance Optimizations

### Go Module Caching
- Caches downloaded modules between runs
- **Speedup**: ~30-60 seconds per service

### Matrix Strategy
- Runs all services in parallel
- **Speedup**: 3x faster than sequential

### Expected Times:
```
Without optimizations: ~15 minutes
With optimizations:     ~5 minutes
```

## 🚨 Common CI Failures

### 1. Test Failures
```bash
# Run locally to debug
go test ./... -v
```

### 2. Lint Errors
```bash
# Fix formatting
go fmt ./...

# Check for issues
go vet ./...
```

### 3. Build Failures
```bash
# Ensure dependencies are up to date
go mod tidy
go mod download
```

### 4. Race Conditions
```bash
# Test with race detector locally
go test ./... -race
```

## 🎨 Status Badges

Add to your README.md:

```markdown
[![CI](https://github.com/bshongwe/services/actions/workflows/ci.yaml/badge.svg)](https://github.com/bshongwe/services/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/gh/bshongwe/services/branch/main/graph/badge.svg)](https://codecov.io/gh/bshongwe/services)
```

## 🔐 Required Secrets (Optional)

For Docker registry push and Codecov:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `DOCKER_USERNAME` | Docker Hub username | No |
| `DOCKER_PASSWORD` | Docker Hub password/token | No |
| `CODECOV_TOKEN` | Codecov upload token | No |

Add secrets at: `Settings → Secrets and variables → Actions`

## 📝 Customization

### Change Go Version
Edit `.github/workflows/ci.yaml`:
```yaml
go-version: '1.23'  # Change here
```

### Add New Service
Add to matrix in workflow:
```yaml
strategy:
  matrix:
    service: [auth-service, user-service, transaction-service, new-service]
```

### Skip CI for Specific Commits
Add to commit message:
```bash
git commit -m "docs: update README [skip ci]"
```

## 🎯 Best Practices

1. **Always run tests locally first**
2. **Keep services small and focused**
3. **Write tests for new features**
4. **Fix linting issues before pushing**
5. **Monitor CI run times**
6. **Review coverage reports regularly**

## 🔄 Workflow File Location

```
.github/
└── workflows/
    └── ci.yaml
```

To update: Edit this file and push to trigger new workflow run.
