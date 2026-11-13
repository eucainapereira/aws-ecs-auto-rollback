terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aws-ecs-auto-rollback-lab"
      Application = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Obtém dinamicamente o Account ID e a Região da conta AWS autenticada
# evitando expor qualquer ID de conta AWS no código-fonte Terraform.
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
