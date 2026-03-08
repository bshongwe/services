data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket         = "platform-tf-state"
    key            = "${var.environment}/terraform.tfstate"
    region         = var.aws_region
  }
}

data "terraform_remote_state" "eks" {
  backend = "s3"
  config = {
    bucket         = "platform-tf-state"
    key            = "${var.environment}/terraform.tfstate"  # same state for simplicity
    region         = var.aws_region
  }
}

resource "aws_msk_cluster" "main" {
  cluster_name           = "${var.project_name}-kafka-${var.environment}"
  kafka_version          = "3.6.0"  # Stable, supports IAM auth
  number_of_broker_nodes = var.broker_nodes_per_az * length(var.azs)

  broker_node_group_info {
    instance_type   = "kafka.m5.large"  # or kafka.t3.small for dev
    ebs_volume_size = 1000
    client_subnets  = data.terraform_remote_state.vpc.outputs.private_app_subnet_ids
    security_groups = [aws_security_group.msk.id]
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  enhanced_monitoring = "PER_BROKER"

  configuration_info {
    arn      = aws_msk_configuration.main.arn
    revision = aws_msk_configuration.main.latest_revision
  }

  tags = {
    Environment = var.environment
  }
}

resource "aws_msk_configuration" "main" {
  name = "${var.project_name}-kafka-config"

  kafka_versions = ["3.6.0"]

  server_properties = <<PROPERTIES
auto.create.topics.enable = false
min.insync.replicas = 2
default.replication.factor = 3
PROPERTIES
}

resource "aws_kms_key" "msk" {
  description             = "MSK encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_security_group" "msk" {
  name        = "${var.project_name}-msk-sg"
  description = "Security group for MSK cluster"
  vpc_id      = data.terraform_remote_state.vpc.outputs.vpc_id

  ingress {
    from_port       = 9098  # IAM auth port
    to_port         = 9098
    protocol        = "tcp"
    security_groups = [data.terraform_remote_state.eks.outputs.cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Kafka Provider Configuration (requires bootstrap servers from MSK)
terraform {
  required_providers {
    kafka = {
      source  = "Mongey/kafka"
      version = "~> 0.7.0"
    }
  }
}

provider "kafka" {
  bootstrap_servers = [aws_msk_cluster.main.bootstrap_brokers_tls]
  tls_enabled       = true

  # For IAM authentication
  sasl_mechanism = "SCRAM-SHA-512"
  sasl_username  = var.kafka_admin_username
  sasl_password  = var.kafka_admin_password
}

# Create initial topics for the platform
resource "kafka_topic" "user_events" {
  name               = "user-events"
  replication_factor = 3
  partitions         = 6

  config = {
    "retention.ms"           = "604800000"  # 7 days
    "segment.ms"             = "3600000"    # 1 hour
    "min.insync.replicas"    = "2"
    "cleanup.policy"         = "delete"
    "compression.type"       = "snappy"
  }
}

resource "kafka_topic" "transaction_events" {
  name               = "transaction-events"
  replication_factor = 3
  partitions         = 12  # Higher for transaction volume

  config = {
    "retention.ms"           = "2592000000"  # 30 days
    "segment.ms"             = "3600000"     # 1 hour
    "min.insync.replicas"    = "2"
    "cleanup.policy"         = "delete"
    "compression.type"       = "snappy"
  }
}

resource "kafka_topic" "auth_events" {
  name               = "auth-events"
  replication_factor = 3
  partitions         = 6

  config = {
    "retention.ms"           = "2592000000"  # 30 days
    "segment.ms"             = "3600000"     # 1 hour
    "min.insync.replicas"    = "2"
    "cleanup.policy"         = "delete"
    "compression.type"       = "snappy"
  }
}

resource "kafka_topic" "audit_logs" {
  name               = "audit-logs"
  replication_factor = 3
  partitions         = 6

  config = {
    "retention.ms"           = "15552000000"  # 180 days (6 months)
    "segment.ms"             = "86400000"     # 24 hours
    "min.insync.replicas"    = "2"
    "cleanup.policy"         = "delete"
    "compression.type"       = "snappy"
  }
}

resource "kafka_topic" "dead_letter_queue" {
  name               = "dead-letter-queue"
  replication_factor = 3
  partitions         = 3

  config = {
    "retention.ms"           = "2592000000"  # 30 days
    "segment.ms"             = "3600000"     # 1 hour
    "min.insync.replicas"    = "2"
    "cleanup.policy"         = "delete"
    "compression.type"       = "snappy"
  }
}

# ACLs for service access (IAM-based alternative recommended for production)
resource "kafka_acl" "auth_service_producer" {
  resource_name       = "auth-events"
  resource_type       = "Topic"
  acl_principal       = "User:auth-service"
  acl_host            = "*"
  acl_operation       = "Write"
  acl_permission_type = "Allow"
}

resource "kafka_acl" "user_service_producer" {
  resource_name       = "user-events"
  resource_type       = "Topic"
  acl_principal       = "User:user-service"
  acl_host            = "*"
  acl_operation       = "Write"
  acl_permission_type = "Allow"
}

resource "kafka_acl" "transaction_service_producer" {
  resource_name       = "transaction-events"
  resource_type       = "Topic"
  acl_principal       = "User:transaction-service"
  acl_host            = "*"
  acl_operation       = "Write"
  acl_permission_type = "Allow"
}