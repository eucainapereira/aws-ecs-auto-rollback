# ==============================================================================
# Amazon ECR - Repositório de Imagens Docker da Aplicação
# ==============================================================================
resource "aws_ecr_repository" "clientes_app" {
  name                 = "clientes-app"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "clientes-app"
  }
}

# Política de ciclo de vida para manter apenas as últimas 10 imagens e evitar custos
resource "aws_ecr_lifecycle_policy" "clientes_app" {
  repository = aws_ecr_repository.clientes_app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Manter apenas as 10 imagens mais recentes"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

