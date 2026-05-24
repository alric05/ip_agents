provider "aws" {
  region = var.region
}

terraform {
  required_version = "1.9.3"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.76.0, < 6.0.0"
    }
  }

  # Do NOT modify - values will be filled in via templated variables
  backend "s3" {
    bucket         = "managed_by_template"
    key            = "managed_by_template"
    region         = "managed_by_template"
    dynamodb_table = "managed_by_template"
    encrypt        = true
  }
}