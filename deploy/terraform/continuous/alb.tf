module "ecs_alb" {
  source = "git::https://github.com/clarivate-prod/platform-tf-aws-lb.git?ref=master"

  # Module will include env_name automatically
  name            = local.short_app_name
  vpc_id          = var.vpc_id
  truncate_name   = true
  security_groups = [aws_security_group.lb-sg0.id, aws_security_group.lb-sg1.id, aws_security_group.lb-sg2.id, aws_security_group.lb-sg3.id]
  subnets         = split(",", var.private_subnets)
  env_name        = var.env_name
  enable_lb_logs  = (local.major_env == "prod" ? true : false)

  tags = merge(
    local.common_tags,
    var.tags,
    { "Name" = local.service_name },
    { "Component" = "alb" },
    { "tr:role" = "alb" }
  )

  idle_timeout = 4000

  http_listeners = [
    {
      port        = 80
      protocol    = "HTTP"
      action_type = "redirect"
      redirect = {
        port        = 443
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  ]

  https_listeners = [
    {
      port               = 443
      protocol           = "HTTPS"
      action_type        = "forward"
      target_group_index = 0
      certificate_arn    = var.acm_certificate_arn
    }
  ]

  target_groups = [
    {
      port        = var.listener_port
      protocol    = "HTTP"
      target_type = "ip"
      health_check = {
        enabled             = true
        path                = var.healthcheck_path
        port                = var.healthcheck_port
        matcher             = "200"
        unhealthy_threshold = 6
      }

      deregistration_delay = 60
      slow_start           = 30
    }
  ]
}

#----------------------------------------
# ALB Security Groups
#----------------------------------------
resource "aws_security_group" "lb-sg0" {
  description = "allow 80/443 inbound traffic from VPC and API GW networks"
  name        = "ielb_${local.service_name}-lb-sg0"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    var.tags,
    { "Name" = "${local.service_name}-lb-sg0" },
    { "Component" = "sg" },
    { "tr:role" = "sg" }
  )
}

resource "aws_security_group_rule" "lb-sg0_egress" {
  description       = "allow all outbound traffic"
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.lb-sg0.id
}

resource "aws_security_group_rule" "lb-sg0_rule0" {
  description       = "allow HTTP from VPC"
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = split(",", var.vpc_cidr)
  security_group_id = aws_security_group.lb-sg0.id
}

resource "aws_security_group_rule" "lb-sg0_rule1" {
  description       = "allow HTTPS from VPC"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = split(",", var.vpc_cidr)
  security_group_id = aws_security_group.lb-sg0.id
}

resource "aws_security_group_rule" "lb-sg0_rule2" {
  description       = "allow HTTP from API-GW VPC"
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = var.alb_consumer_cidrs
  security_group_id = aws_security_group.lb-sg0.id
}

resource "aws_security_group_rule" "lb-sg0_rule3" {
  description       = "allow HTTPS from API-GW VPC"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.alb_consumer_cidrs
  security_group_id = aws_security_group.lb-sg0.id
}

resource "aws_security_group" "lb-sg1" {
  description = "allow 80 inbound traffic from internal networks"
  name        = "ielb_${local.service_name}-lb-sg1"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    var.tags,
    { "Name" = "${local.service_name}-lb-sg1" },
    { "Component" = "sg" },
    { "tr:role" = "sg" }
  )
}

resource "aws_security_group_rule" "lb-sg1_rule0" {
  description       = "allow 80 inbound traffic from internal networks"
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  prefix_list_ids   = [data.aws_ec2_managed_prefix_list.clvt_internal_allow.id]
  security_group_id = aws_security_group.lb-sg1.id
}

resource "aws_security_group" "lb-sg2" {
  description = "allow 443 inbound traffic from internal networks"
  name        = "ielb_${local.service_name}-lb-sg2"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    var.tags,
    { "Name" = "${local.service_name}-lb-sg2" },
    { "Component" = "sg" },
    { "tr:role" = "sg" }
  )
}

resource "aws_security_group_rule" "lb-sg2_rule0" {
  description       = "allow 443 inbound traffic from internal networks"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  prefix_list_ids   = [data.aws_ec2_managed_prefix_list.clvt_internal_allow.id]
  security_group_id = aws_security_group.lb-sg2.id
}


resource "aws_security_group" "lb-sg3" {
    name        = "ielb_${local.service_name}-lb-sg3"
    description = "Allow 443 inbound traffic from Databricks"
    vpc_id      = var.vpc_id

    lifecycle {
        create_before_destroy = true
    }

    tags = (merge(
        local.common_tags,
        var.tags,
        { "Name" = "${local.service_name}-lb-sg3" },
        { "tr:role" = "sg" },
    ))
}

#----------------------------------------
# ALB DNS Alias Entry
#----------------------------------------
resource "aws_route53_record" "ecs_load_balancer" {
  zone_id = var.env_public_hosted_zone
  name    = "${local.long_service_name}.${var.env_public_dns}"
  type    = "A"
  alias {
    name                   = module.ecs_alb.dns_name[0]
    zone_id                = module.ecs_alb.zone_id[0]
    evaluate_target_health = true
  }
}
