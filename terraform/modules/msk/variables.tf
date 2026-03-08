variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "azs" {
  description = "Availability zones"
  type        = list(string)
}

variable "broker_nodes_per_az" {
  description = "Number of broker nodes per availability zone"
  type        = number
  default     = 1
}

variable "kafka_admin_username" {
  description = "Kafka admin username for SASL authentication"
  type        = string
  sensitive   = true
}

variable "kafka_admin_password" {
  description = "Kafka admin password for SASL authentication"
  type        = string
  sensitive   = true
}
