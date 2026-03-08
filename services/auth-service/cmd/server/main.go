package main

import (
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"your-org/platform-services/auth-service/internal/database"
	"your-org/platform-services/auth-service/internal/handler"
	"your-org/platform-services/auth-service/internal/repository"
	"your-org/platform-services/auth-service/internal/service"
	"your-org/platform-services/shared/logging"
)

func main() {
	logger, _ := logging.NewProduction()
	defer logger.Sync()

	// Initialize database
	dbConfig := database.LoadConfigFromEnv()
	db, err := database.Connect(dbConfig)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	// Run migrations
	if err := database.Migrate(db); err != nil {
		log.Fatalf("Failed to run migrations: %v", err)
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
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
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
	addr := ":" + port

	logger.Info("Starting Auth Service", zap.String("port", addr))
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

