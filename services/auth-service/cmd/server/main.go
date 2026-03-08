package main

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"your-org/platform-services/shared/logging"
	"your-org/platform-services/auth-service/internal/handler"
)

func main() {
	logger, _ := logging.NewProductionLogger()
	defer logger.Sync()

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

	port := ":8080"
	logger.Info("Starting Auth Service", zap.String("port", port))
	if err := r.Run(port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
