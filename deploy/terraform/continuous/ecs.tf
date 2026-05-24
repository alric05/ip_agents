#----------------------------------------
# ECS Cluster
#----------------------------------------
resource "aws_ecs_cluster" "product-cluster" {
    name = local.long_service_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = merge(
    local.common_tags,
    { "Name" = local.long_service_name },
    { "Component" = "ecs-cluster" },
    { "tr:role" = "ecs-cluster" }
  )
}

resource "aws_ecs_cluster_capacity_providers" "product-cluster" {
  cluster_name = aws_ecs_cluster.product-cluster.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    base              = 0
    weight            = 100
  }
}

#----------------------------------------
# ECS Task
#----------------------------------------
resource "aws_ecs_task_definition" "ecs_task" {
  family                   = local.long_service_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_mem
  task_role_arn            = aws_iam_role.ecs_container_role.arn
  execution_role_arn       = aws_iam_role.ecs_container_role.arn

  depends_on = [
    aws_cloudwatch_log_group.service_log_group
  ]

  # ECS Container Definitions
    container_definitions = <<SERVICECONFIG
    [
      {
        "name": "${local.long_service_name}",
        "image": "platform-docker.repo.clarivate.io/${var.app_family}/${var.app_name}:${var.app_version}",
        "essential": true,
        "logConfiguration": {
          "logDriver": "awslogs",
          "options": {
            "awslogs-group": "/ecs/${var.app_family}/${var.app_name}/${var.env_name}",
            "awslogs-region": "${var.main_region}",
            "awslogs-stream-prefix": "${var.app_name}"
          }
        },
        "ulimits": [
          {
            "name": "nofile",
            "softLimit": 50000,
            "hardLimit": 50000
          }
        ],
        "cpu": 0,
        "mountPoints": [],
        "volumesFrom": [],
        "portMappings": [
          {
            "containerPort": ${var.listener_port},
            "hostPort": ${var.listener_port},
            "protocol": "tcp"
          }
        ],
        "environment": [
          {
            "name": "APP_NAME",
            "value": "${var.app_name}"
          },
          {
            "name": "APP_ENV",
            "value": "${var.env_name}"
          },
          {
            "name": "APP_REGION",
            "value": "${var.region}"
          },
          {
            "name": "METRICS_ENABLED",
            "value": "${var.metrics_enabled}"
          },
          {
            "name": "OTEL_SDK_DISABLED",
            "value": "true"
          },
          {
            "name": "GUARDRAILS_DISABLE_ANALYTICS",
            "value": "true"
          },
          {
            "name": "GUARDRAILS_NO_UPDATE_CHECK",
            "value": "true"
          }
        ],
        "secrets": [
          {
            "name": "ANTHROPIC_API_KEY",
            "valueFrom": "${aws_secretsmanager_secret.anthropic_api_key.arn}"
          },
          {
            "name": "AZURE_OPENAI_API_KEY",
            "valueFrom": "${aws_secretsmanager_secret.azure_openai_api_key.arn}"
          },
          {
            "name": "AZURE_OPENAI_ENDPOINT",
            "valueFrom": "${aws_secretsmanager_secret.azure_openai_endpoint.arn}"
          },
          {
            "name": "AZURE_OPENAI_DEPLOYMENT_NAME",
            "valueFrom": "${aws_secretsmanager_secret.azure_openai_deployment_name.arn}"
          },
          {
            "name": "DERWENT_API_BASE_URL",
            "valueFrom": "${aws_secretsmanager_secret.derwent_api_base_url.arn}"
          },
          {
            "name": "AZURE_OPENAI_API_VERSION",
            "valueFrom": "${aws_secretsmanager_secret.azure_openai_api_version.arn}"
          },
          {
            "name": "INNOGRAPHY_USER_NAME",
            "valueFrom": "${aws_secretsmanager_secret.innography_user_name.arn}"
          },
          {
            "name": "INNOGRAPHY_USER_SECRET",
            "valueFrom": "${aws_secretsmanager_secret.innography_user_secret.arn}"
          },
          {
            "name": "INNOGRAPHY_USER_TOKEN",
            "valueFrom": "${aws_secretsmanager_secret.innography_user_token.arn}"
          },
          {
            "name": "INNOGRAPHY_TOKEN_URL",
            "valueFrom": "${aws_secretsmanager_secret.innography_token_url.arn}"
          },
          {
            "name": "INNOGRAPHY_SERVICES_URL",
            "valueFrom": "${aws_secretsmanager_secret.innography_services_url.arn}"
          }
        ]
      }
    ]
SERVICECONFIG

  tags = merge(
    local.common_tags,
    { "Name" = local.long_service_name },
    { "tr:role" = "ecs-task" }
  )
}

#----------------------------------------
# ECS Service
#----------------------------------------
resource "aws_ecs_service" "ecs_service" {
  name                               = local.long_service_name
  cluster                            = local.long_service_name
  task_definition                    = aws_ecs_task_definition.ecs_task.arn
  desired_count                      = var.ecs_autoscaling_desired
  propagate_tags                     = "SERVICE"
  platform_version                   = var.ecs_platform_version
  enable_execute_command             = true
  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100
  wait_for_steady_state              = var.ecs_deploy_wait_for_steady_state

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    security_groups = [aws_security_group.ecs_container_security_group.id]
    subnets         = split(",", var.private_subnets)
  }

  capacity_provider_strategy {
    capacity_provider = var.ecs_launchtype
    weight            = "100"
  }

  load_balancer {
    target_group_arn = module.ecs_alb.target_group_arns[0]
    container_name   = local.long_service_name
    container_port   = var.listener_port
  }

  depends_on = [
    module.ecs_alb
  ]

  tags = merge(
    local.common_tags,
    { "Name" = "${var.app_family}-${var.app_name}-${var.env_name}" },
    { "tr:role" = "ecs-service" }
  )
}

#----------------------------------------
# ECS Security Groups
#----------------------------------------
resource "aws_security_group" "ecs_container_security_group" {
  description = "SG for running ECS containers"
  name        = "ecs-${local.long_service_name}"
  vpc_id      = var.vpc_id

  tags = merge(
    local.common_tags,
    { "Name" = "ecs-${local.long_service_name}" },
    { "Component" = "sg" },
    { "tr:role" = "sg" }
  )
}

resource "aws_security_group_rule" "common_sg_egress" {
  description       = "allow all outbound traffic"
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.ecs_container_security_group.id
}

resource "aws_security_group_rule" "common_sg_self" {
  description       = "allow all incoming traffic"
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  self              = "true"
  security_group_id = aws_security_group.ecs_container_security_group.id
}

resource "aws_security_group_rule" "common_sg_bastion" {
  description              = "allow traffic from bastion"
  for_each                 = toset(split(",", var.ecs_bastion_ingress_ports))
  type                     = "ingress"
  from_port                = each.value
  to_port                  = each.value
  protocol                 = "tcp"
  source_security_group_id = data.aws_security_group.bastion_sg.id
  security_group_id        = aws_security_group.ecs_container_security_group.id
}

# Allow the ALB to connect to any port on the running container
resource "aws_security_group_rule" "common_sg_lb" {
  description              = "allow all traffic from ALB"
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = aws_security_group.lb-sg0.id
  security_group_id        = aws_security_group.ecs_container_security_group.id
}

#----------------------------------------
# ECS Application Autoscaling
#----------------------------------------
resource "aws_appautoscaling_target" "ecs_target" {
  min_capacity       = element(split(",", var.ecs_autoscaling_minmax), 0)
  max_capacity       = element(split(",", var.ecs_autoscaling_minmax), 1)
  resource_id        = "service/${local.long_service_name}/${aws_ecs_service.ecs_service.name}"
  role_arn           = "arn:aws:iam::${var.account_id}:role/aws-service-role/ecs.application-autoscaling.amazonaws.com/AWSServiceRoleForApplicationAutoScaling_ECSService"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_alb_target_tracking_policy" {
  count = (local.major_env == "prod" ? 1 : 0)

  name               = "alb-active-request-count-scale-up"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = var.ecs_autoscaling_target_value

    predefined_metric_specification {
      predefined_metric_type = var.ecs_autoscaling_target_metric
      resource_label         = format("%s/%s", module.ecs_alb.arn_suffix[0], module.ecs_alb.target_group_arn_suffixes[0])
    }
  }
}

#----------------------------------------
# ECS Cloudwatch logging
#----------------------------------------
resource "aws_cloudwatch_log_group" "service_log_group" {
  name              = "/ecs/${var.app_family}/${var.app_name}/${var.env_name}"
  retention_in_days = 30

  # tags are not yet standard for this resource type
  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}" },
    { "tr:role" = "cw-loggroup" },
  )
}