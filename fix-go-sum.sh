#!/bin/bash
# Fix go.sum sync issues for auth-service and shared modules
# Run this script from the repository root: /Users/ernie-dev/Documents/services

set -e  # Exit on error

echo "🔧 Fixing go.sum sync issues..."
echo ""

# Step 1: Fix auth-service
echo "📦 Step 1/4: Tidying auth-service dependencies..."
cd services/auth-service
go mod tidy
echo "✅ auth-service go.sum updated"
echo ""

# Step 2: Fix shared/logging module
echo "📦 Step 2/4: Tidying shared/logging module..."
cd ../../shared/logging
go mod tidy
echo "✅ shared/logging go.sum updated"
echo ""

# Step 3: Fix shared/auth module
echo "📦 Step 3/4: Tidying shared/auth module..."
cd ../auth
go mod tidy
echo "✅ shared/auth go.sum updated"
echo ""

# Step 4: Fix shared/config module
echo "📦 Step 4/4: Tidying shared/config module..."
cd ../config
go mod tidy
echo "✅ shared/config go.sum updated"
echo ""

# Verify auth-service builds
echo "🔍 Verifying auth-service..."
cd ../../services/auth-service
go vet ./...
echo "✅ go vet passed!"
echo ""

# Optional: Build to confirm
echo "🏗️  Building auth-service..."
go build -o ../../bin/auth-service ./cmd/server
echo "✅ Build successful!"
echo ""

echo "🎉 All fixes complete! Ready to commit."
echo ""
echo "Next steps:"
echo "  git add services/auth-service/go.sum"
echo "  git add shared/logging/go.sum"
echo "  git add shared/auth/go.sum"
echo "  git add shared/config/go.sum"
echo "  git commit -m 'fix: update go.sum for auth-service and shared modules'"
echo "  git push origin main"
