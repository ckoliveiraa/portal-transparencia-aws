variable "region" {
  description = "Região AWS"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Nome (único global) do bucket do data lake"
  type        = string
}

variable "secret_name" {
  description = "Nome do segredo com a chave-api-dados no Secrets Manager"
  type        = string
  default     = "portal-transparencia/chave-api-dados"
}

variable "api_key" {
  description = "Valor da chave-api-dados (passe via TF_VAR_api_key, NUNCA commitado)"
  type        = string
  sensitive   = true
}

variable "schedule_expression" {
  description = "Frequência de re-invocação da Lambda worker"
  type        = string
  default     = "rate(15 minutes)"
}

variable "ano_mes" {
  description = "Payload de coleta (ano/mes) enviado pelo schedule"
  type        = object({ ano = number, mes = number })
  default     = { ano = 2024, mes = 1 }
}
