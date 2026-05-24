locals {  
  s3_data_env_suffix = var.env_name == "prod" ? "prod" : contains(["dev-snapshot", "dev-stable"], var.env_name) ? "dev" : ""
}