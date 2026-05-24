resource "aws_security_group" "dpa_api" {
    name        = "dpa_api_${local.long_service_name}"
    description = "Managed by Terraform - DPA API SG for ${local.long_service_name}"
    vpc_id      = var.vpc_id

    tags = local.common_tags
}

resource "aws_security_group_rule" "dpa_api_allow_vpc_access_8000" {
    type              = "ingress"
    from_port         = "8000"
    to_port           = "8000"
    protocol          = "tcp"
    cidr_blocks       = [data.aws_vpc.vpc.cidr_block]
    security_group_id = aws_security_group.dpa_api.id
    description       = "Allow VPC ingress on 8000"
}

resource "aws_security_group_rule" "dpa_api_egress_rule" {
    type              = "egress"
    from_port         = var.all
    to_port           = var.all
    protocol          = var.all
    cidr_blocks       = ["0.0.0.0/0"]
    security_group_id = aws_security_group.dpa_api.id
}
