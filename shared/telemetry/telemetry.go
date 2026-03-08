package telemetry

import (
	"context"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"go.opentelemetry.io/otel/trace"
)

// Config holds telemetry configuration
type Config struct {
	ServiceName    string
	ServiceVersion string
	Environment    string
}

// InitTracer initializes OpenTelemetry tracing
func InitTracer(cfg Config) (func(context.Context) error, error) {
	// Create stdout exporter (for development)
	exporter, err := stdouttrace.New(
		stdouttrace.WithPrettyPrint(),
	)
	if err != nil {
		return nil, err
	}

	// Create resource
	res, err := resource.New(
		context.Background(),
		resource.WithAttributes(
			semconv.ServiceName(cfg.ServiceName),
			semconv.ServiceVersion(cfg.ServiceVersion),
			semconv.DeploymentEnvironment(cfg.Environment),
		),
	)
	if err != nil {
		return nil, err
	}

	// Create tracer provider
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	// Register as global tracer provider
	otel.SetTracerProvider(tp)

	// Return shutdown function
	return tp.Shutdown, nil
}

// StartSpan creates a new span with the given name
func StartSpan(ctx context.Context, tracerName, spanName string) (context.Context, trace.Span) {
	tracer := otel.Tracer(tracerName)
	return tracer.Start(ctx, spanName)
}

// RecordError records an error in the current span
func RecordError(span trace.Span, err error) {
	if err != nil {
		span.RecordError(err)
	}
}

// AddEvent adds an event to the current span
func AddEvent(span trace.Span, name string, attrs ...interface{}) {
	span.AddEvent(name)
}

// MeasureDuration measures the duration of a function
func MeasureDuration(ctx context.Context, tracerName, operationName string, fn func() error) error {
	start := time.Now()
	ctx, span := StartSpan(ctx, tracerName, operationName)
	defer span.End()

	err := fn()
	duration := time.Since(start)
	
	span.SetAttributes(
		semconv.HTTPRequestMethodKey.String(operationName),
	)
	
	if err != nil {
		RecordError(span, err)
	}
	
	span.AddEvent("operation completed", 
		trace.WithAttributes(
			semconv.HTTPResponseStatusCodeKey.Int(200),
		),
	)
	
	_ = duration // Can be used for metrics
	return err
}
