package handler_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/bshongwe/services/auth-service/internal/handler"
	"github.com/bshongwe/services/auth-service/internal/model"
	"github.com/bshongwe/services/auth-service/internal/repository"
	"github.com/bshongwe/services/auth-service/internal/service"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to open test database: %v", err)
	}

	// Auto migrate
	if err := db.AutoMigrate(&model.User{}); err != nil {
		t.Fatalf("Failed to migrate: %v", err)
	}

	return db
}

func TestRegister(t *testing.T) {
	gin.SetMode(gin.TestMode)

	db := setupTestDB(t)
	userRepo := repository.NewUserRepository(db)
	authService := service.NewAuthService(userRepo, "test-secret")
	authHandler := handler.NewAuthHandler(authService)

	router := gin.New()
	router.POST("/auth/register", authHandler.Register)

	tests := []struct {
		name           string
		payload        map[string]string
		expectedStatus int
		checkResponse  func(*testing.T, map[string]interface{})
	}{
		{
			name: "Valid registration",
			payload: map[string]string{
				"email":    "test@example.com",
				"password": "password123",
			},
			expectedStatus: http.StatusCreated,
			checkResponse: func(t *testing.T, resp map[string]interface{}) {
				assert.Equal(t, "User registered successfully", resp["message"])
				assert.NotEmpty(t, resp["user_id"])
				assert.Equal(t, "test@example.com", resp["email"])
			},
		},
		{
			name: "Invalid email",
			payload: map[string]string{
				"email":    "invalid-email",
				"password": "password123",
			},
			expectedStatus: http.StatusBadRequest,
		},
		{
			name: "Password too short",
			payload: map[string]string{
				"email":    "test@example.com",
				"password": "short",
			},
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			body, _ := json.Marshal(tt.payload)
			req := httptest.NewRequest(http.MethodPost, "/auth/register", bytes.NewBuffer(body))
			req.Header.Set("Content-Type", "application/json")

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)

			if tt.checkResponse != nil {
				var response map[string]interface{}
				json.Unmarshal(w.Body.Bytes(), &response)
				tt.checkResponse(t, response)
			}
		})
	}
}

func TestLogin(t *testing.T) {
	gin.SetMode(gin.TestMode)

	db := setupTestDB(t)
	userRepo := repository.NewUserRepository(db)
	authService := service.NewAuthService(userRepo, "test-secret")
	authHandler := handler.NewAuthHandler(authService)

	// Register a test user first
	_, err := authService.Register("test@example.com", "password123")
	assert.NoError(t, err)

	router := gin.New()
	router.POST("/auth/login", authHandler.Login)

	tests := []struct {
		name           string
		payload        map[string]string
		expectedStatus int
		checkResponse  func(*testing.T, map[string]interface{})
	}{
		{
			name: "Valid login",
			payload: map[string]string{
				"email":    "test@example.com",
				"password": "password123",
			},
			expectedStatus: http.StatusOK,
			checkResponse: func(t *testing.T, resp map[string]interface{}) {
				assert.Equal(t, "Login successful", resp["message"])
				assert.NotEmpty(t, resp["token"])
			},
		},
		{
			name: "Invalid password",
			payload: map[string]string{
				"email":    "test@example.com",
				"password": "wrongpassword",
			},
			expectedStatus: http.StatusUnauthorized,
		},
		{
			name: "Non-existent user",
			payload: map[string]string{
				"email":    "nonexistent@example.com",
				"password": "password123",
			},
			expectedStatus: http.StatusUnauthorized,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			body, _ := json.Marshal(tt.payload)
			req := httptest.NewRequest(http.MethodPost, "/auth/login", bytes.NewBuffer(body))
			req.Header.Set("Content-Type", "application/json")

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)

			if tt.checkResponse != nil {
				var response map[string]interface{}
				json.Unmarshal(w.Body.Bytes(), &response)
				tt.checkResponse(t, response)
			}
		})
	}
}
