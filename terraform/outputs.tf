output "alb_dns_name" {
  description = "DNS público do Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_url" {
  description = "URL completa para acessar o Portal de Clientes no navegador"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecs_cluster_name" {
  description = "Nome do Cluster Amazon ECS"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Nome do Serviço Amazon ECS monitorado pelo Deployment Circuit Breaker"
  value       = aws_ecs_service.app.name
}

output "ecs_task_definition_family" {
  description = "Família da Task Definition do ECS"
  value       = aws_ecs_task_definition.app.family
}

output "ecr_repository_url" {
  description = "URI do repositório Amazon ECR para push das imagens Docker"
  value       = aws_ecr_repository.clientes_app.repository_url
}

output "dynamodb_table_name" {
  description = "Nome da tabela Amazon DynamoDB de clientes"
  value       = aws_dynamodb_table.clientes.name
}

output "github_actions_role_arn" {
  description = "ARN da IAM Role OIDC para configurar no secret AWS_ROLE_ARN do GitHub Actions"
  value       = aws_iam_role.github_actions_ecs_deploy.arn
}
