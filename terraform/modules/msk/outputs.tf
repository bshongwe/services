output "cluster_arn" {
  description = "ARN of the MSK cluster"
  value       = aws_msk_cluster.main.arn
}

output "bootstrap_brokers_tls" {
  description = "TLS bootstrap brokers"
  value       = aws_msk_cluster.main.bootstrap_brokers_tls
  sensitive   = true
}

output "bootstrap_brokers_sasl_iam" {
  description = "IAM SASL bootstrap brokers"
  value       = aws_msk_cluster.main.bootstrap_brokers_sasl_iam
  sensitive   = true
}

output "zookeeper_connect_string" {
  description = "Zookeeper connection string"
  value       = aws_msk_cluster.main.zookeeper_connect_string
  sensitive   = true
}

output "security_group_id" {
  description = "Security group ID for MSK cluster"
  value       = aws_security_group.msk.id
}

output "topics" {
  description = "List of created Kafka topics"
  value = {
    user_events        = kafka_topic.user_events.name
    transaction_events = kafka_topic.transaction_events.name
    auth_events        = kafka_topic.auth_events.name
    audit_logs         = kafka_topic.audit_logs.name
    dead_letter_queue  = kafka_topic.dead_letter_queue.name
  }
}
