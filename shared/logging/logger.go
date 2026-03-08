package logging

import (
	"os"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// NewProduction creates a production-ready logger with caller information
func NewProduction() (*zap.Logger, error) {
	return zap.NewProduction(zap.WithCaller(true))
}

// NewDevelopment creates a development logger with pretty printing
func NewDevelopment() (*zap.Logger, error) {
	return zap.NewDevelopment()
}

// NewLogger creates a logger based on environment
func NewLogger() (*zap.Logger, error) {
	env := os.Getenv("ENV")
	if env == "production" {
		return NewProduction()
	}
	return NewDevelopment()
}

// Deprecated: Use NewProduction instead
func NewProductionLogger() (*zap.Logger, error) {
	return NewProduction()
}

// Deprecated: Use NewDevelopment instead
func NewDevelopmentLogger() (*zap.Logger, error) {
	return NewDevelopment()
}

// NewLoggerWithLevel creates a logger with custom level
func NewLoggerWithLevel(level string) (*zap.Logger, error) {
	var zapLevel zapcore.Level
	if err := zapLevel.UnmarshalText([]byte(level)); err != nil {
		zapLevel = zapcore.InfoLevel
	}

	cfg := zap.NewProductionConfig()
	cfg.Level = zap.NewAtomicLevelAt(zapLevel)
	
	return cfg.Build(zap.WithCaller(true))
}

// WithFields creates a logger with predefined fields
func WithFields(logger *zap.Logger, fields map[string]interface{}) *zap.Logger {
	zapFields := make([]zap.Field, 0, len(fields))
	for key, value := range fields {
		zapFields = append(zapFields, zap.Any(key, value))
	}
	return logger.With(zapFields...)
}
