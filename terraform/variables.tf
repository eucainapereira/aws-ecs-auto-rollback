variable "aws_region" {
  description = "Região da AWS onde os recursos serão provisionados"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nome base do projeto usado para identificação dos recursos"
  type        = string
  default     = "clientes-resilience-lab"
}

variable "environment" {
  description = "Ambiente de execução (lab, dev, prod)"
  type        = string
  default     = "lab"
}

variable "github_repo" {
  description = "Repositório do GitHub autorizado via OIDC no formato owner/repo"
  type        = string
  default     = "eucainapereira/aws-ecs-auto-rollback"
}

variable "create_github_oidc_provider" {
  description = "Define se o provedor OIDC do GitHub deve ser criado (false reutiliza o provedor OIDC já existente na conta via data.aws_caller_identity.current.account_id)"
  type        = bool
  default     = false
}

variable "create_github_oidc_role" {
  description = "Define se a Role IAM github-actions-ecs-deploy-role deve ser criada pelo Terraform (false caso a Role já tenha sido criada previamente na conta)"
  type        = bool
  default     = true
}

variable "container_port" {
  description = "Porta exposta pelo container FastAPI"
  type        = number
  default     = 8000
}

variable "ecs_desired_count" {
  description = "Quantidade desejada de tasks rodando no serviço ECS"
  type        = number
  default     = 1
}

variable "app_version" {
  description = "Versão inicial da aplicação configurada na Task Definition base"
  type        = string
  default     = "v1.0"
}

variable "simulate_failure" {
  description = "Flag inicial de simulação de falha ('false' = saudável, 'true' = retorna HTTP 500 em /health)"
  type        = string
  default     = "false"
}
