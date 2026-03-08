import (
	"context"
	"github.com/segmentio/kafka-go"
	"time"
)

type Transaction struct {
	ID        string  `json:"id"`
	UserID    string  `json:"user_id"`
	Amount    float64 `json:"amount"`
	CreatedAt time.Time
}

func (s *TransactionService) Create(tx Transaction) error {
	// Save to DB...

	// Produce event
	writer := &kafka.Writer{
		Addr:     kafka.TCP("b-1.example.msk.us-east-1.amazonaws.com:9098"), // from terraform output
		Topic:    "transactions.created",
		Balancer: &kafka.LeastBytes{},
		Async:    false, // sync for MVP
	}

	msg := kafka.Message{
		Key:   []byte(tx.ID),
		Value: []byte(fmt.Sprintf(`{"event":"transaction.created","tx_id":"%s","user_id":"%s","amount":%.2f}`, tx.ID, tx.UserID, tx.Amount)),
	}

	if err := writer.WriteMessages(context.Background(), msg); err != nil {
		logger.Error("Failed to produce event", zap.Error(err))
		return err
	}

	return nil
}

// In prod: Use IAM auth (aws-msk-iam-auth jar or Go IAM signer lib), fetch bootstrap from secrets manager
// For local/dev: Use Dockerized Kafka/Zookeeper