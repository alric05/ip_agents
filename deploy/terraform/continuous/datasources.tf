data "aws_vpc" "vpc" {
  id = var.vpc_id
}

data "aws_security_group" "bastion_sg" {
  name   = var.bastion_sg_name
  vpc_id = var.vpc_id
}

data "aws_ec2_managed_prefix_list" "clvt_internal_allow" {
  filter {
    name   = "prefix-list-name"
    values = ["clvt-internal-allow"]
  }
}