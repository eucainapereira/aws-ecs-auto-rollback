# ==============================================================================
# Amazon DynamoDB - Tabela Serverless On-Demand (PAY_PER_REQUEST)
# ==============================================================================
resource "aws_dynamodb_table" "clientes" {
  name         = "clientes-resilience-lab"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = false
  }

  tags = {
    Name = "clientes-resilience-lab"
  }
}

