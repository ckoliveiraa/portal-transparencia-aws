output "bucket" {
  description = "Nome do bucket do data lake"
  value       = aws_s3_bucket.datalake.id
}

output "lambda_function" {
  description = "Nome da Lambda worker (fatos)"
  value       = aws_lambda_function.worker.function_name
}

output "lambda_dim" {
  description = "Nome da Lambda da dimensão (municípios)"
  value       = aws_lambda_function.dim.function_name
}

output "secret_arn" {
  description = "ARN do segredo com a chave da API"
  value       = aws_secretsmanager_secret.api_key.arn
}

output "glue_database" {
  description = "Database do Glue Catalog"
  value       = aws_glue_catalog_database.transparencia.name
}

output "schedule" {
  description = "Nome do schedule do EventBridge"
  value       = aws_scheduler_schedule.ingestao.name
}
