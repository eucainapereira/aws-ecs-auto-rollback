# ==============================================================================
# Amazon ECS Fargate - Cluster, IAM Roles, Task Definition e Service com Rollback
# ==============================================================================
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-ecs-tasks-sg"
  description = "Permite trafego na porta do container exclusivamente vindo do ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Trafego HTTP vindo apenas do Application Load Balancer"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Saida HTTPS para pull de imagens no ECR, DynamoDB e CloudWatch Logs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ecs-tasks-sg"
  }
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 7

  tags = {
    Name = "/ecs/${var.project_name}"
  }
}

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# ------------------------------------------------------------------------------
# IAM Task Execution Role (Permissão para o agente ECS puxar imagens do ECR e enviar logs)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ------------------------------------------------------------------------------
# IAM Task Role (Menor Privilégio para a aplicação ler/escrever no DynamoDB)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_task_dynamodb_policy" {
  name = "dynamodb-clientes-least-privilege"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBClientesTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.clientes.arn
        ]
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# ECS Task Definition (0.25 vCPU / 0.5 GB RAM)
# ------------------------------------------------------------------------------
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "clientes-app"
      image     = "${aws_ecr_repository.clientes_app.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "APP_VERSION"
          value = var.app_version
        },
        {
          name  = "SIMULATE_FAILURE"
          value = var.simulate_failure
        },
        {
          name  = "DYNAMODB_TABLE"
          value = aws_dynamodb_table.clientes.name
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]

      healthCheck = {
        command = [
          "CMD-SHELL",
          "python -c \"import urllib.request, sys; r = urllib.request.urlopen('http://127.0.0.1:${var.container_port}/health', timeout=3); sys.exit(0 if r.getcode() == 200 else 1)\""
        ]
        interval    = 10
        timeout     = 5
        retries     = 2
        startPeriod = 5
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# ------------------------------------------------------------------------------
# ECS Service com Zero-Downtime (100/200) e Deployment Circuit Breaker + Rollback
# ------------------------------------------------------------------------------
resource "aws_ecs_service" "app" {
  name                              = "${var.project_name}-service"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.app.arn
  desired_count                     = var.ecs_desired_count
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 10

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  # Configuração obrigatória para detecção de falha e Rollback Automático
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "clientes-app"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]

  # Permite que o pipeline de CI/CD atualize as revisões da Task Definition sem conflito com o Terraform
  lifecycle {
    ignore_changes = [task_definition]
  }
}

