package main

import (
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"go.uber.org/zap"

	"github.com/bshongwe/services/auth-service/internal/database"
	"github.com/bshongwe/services/auth-service/internal/handler"
	"github.com/bshongwe/services/auth-service/internal/repository"
	"github.com/bshongwe/services/auth-service/internal/service"
	"github.com/bshongwe/services/shared/logging"
)

var logger *zap.Logger

func main() {
	// Initialize logger with error handling
	var err error
	logger, err = logging.NewProduction()
	if err != nil {
		log.Fatalf("Failed to init logger: %v", err)
	}
	defer logger.Sync()

	// Load .env for local development
	if os.Getenv("ENV") == "dev" {
		if err := godotenv.Load(); err != nil {
			logger.Warn("No .env file found, using environment variables")
		} else {
			logger.Info("Loaded configuration from .env file")
		}
	}

	// Initialize database
	dbConfig := database.LoadConfigFromEnv()
	db, err := database.Connect(dbConfig)
	if err != nil {
		logger.Fatal("Failed to connect to database", zap.Error(err))
	}

	// Run migrations
	if err := database.Migrate(db); err != nil {
		logger.Fatal("Failed to run migrations", zap.Error(err))
	}
	logger.Info("Database migrations completed successfully")

	// Initialize repositories
	userRepo := repository.NewUserRepository(db)

	// Initialize services
	jwtSecret := os.Getenv("JWT_SECRET")
	if jwtSecret == "" {
		jwtSecret = "default-secret-change-in-production"
		logger.Warn("JWT_SECRET not set, using default (not secure for production)")
	}
	authService := service.NewAuthService(userRepo, jwtSecret)

	// Initialize handlers
	authHandler := handler.NewAuthHandler(authService)
	handler.SetGlobalHandler(authHandler)

	r := gin.Default()

	// Health check
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": "auth-service",
		})
	})

	// Auth routes
	auth := r.Group("/auth")
	{
		auth.POST("/register", handler.Register)
		auth.POST("/login", handler.Login)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	logger.Info("Auth Service starting", zap.String("port", port))
	if err := r.Run(":" + port); err != nil {
		logger.Fatal("Server failed", zap.Error(err))
	}
}

