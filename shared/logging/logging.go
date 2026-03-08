package logging

import "go.uber.org/zap"

func NewProductionLogger() (*zap.Logger, error) {
	return zap.NewProduction()
}