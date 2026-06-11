terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# S3 — data lake (raw + curated)
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "datalake" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket                  = aws_s3_bucket.datalake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# Secrets Manager — chave da API
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "api_key" {
  name = var.secret_name
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id     = aws_secretsmanager_secret.api_key.id
  secret_string = jsonencode({ "chave-api-dados" = var.api_key })
}

# ---------------------------------------------------------------------------
# IAM — role da Lambda (least privilege)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "lambda" {
  name = "transparencia-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "transparencia-lambda-policy"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.datalake.arn, "${aws_s3_bucket.datalake.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.api_key.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Lambda worker — ingestão dos fatos
# (empacota src/lambda; 'requests' deve vir numa layer — ver README do módulo 04)
# ---------------------------------------------------------------------------
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda"
  output_path = "${path.module}/build/lambda.zip"
}

resource "aws_lambda_function" "worker" {
  function_name    = "transparencia-ingestao-worker"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 900
  memory_size      = 256
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      BUCKET      = aws_s3_bucket.datalake.id
      SECRET_NAME = var.secret_name
    }
  }
  # layers = [aws_lambda_layer_version.requests.arn]  # crie a layer (módulo 04)
}

# Lambda DIM — ingere a dimensão de municípios (IBGE) direto no S3.
# Compartilha o mesmo zip e role; só muda o handler. Rode sob demanda (dim é estática).
resource "aws_lambda_function" "dim" {
  function_name    = "transparencia-ingestao-dim"
  role             = aws_iam_role.lambda.arn
  handler          = "handler_dim.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      BUCKET = aws_s3_bucket.datalake.id
    }
  }
  # layers = [aws_lambda_layer_version.requests.arn]  # mesma layer do worker
}

# ---------------------------------------------------------------------------
# EventBridge Scheduler — re-invoca a Lambda
# ---------------------------------------------------------------------------
resource "aws_iam_role" "scheduler" {
  name = "transparencia-scheduler-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "transparencia-scheduler-policy"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.worker.arn
    }]
  })
}

resource "aws_scheduler_schedule" "ingestao" {
  name                = "transparencia-ingestao"
  schedule_expression = var.schedule_expression
  flexible_time_window { mode = "OFF" }

  target {
    arn      = aws_lambda_function.worker.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode(var.ano_mes)
  }
}

# ---------------------------------------------------------------------------
# Glue — database (job e crawler ficam como exercício do módulo; ver README 06/07)
# ---------------------------------------------------------------------------
resource "aws_glue_catalog_database" "transparencia" {
  name = "transparencia"
}
