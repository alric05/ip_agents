#----------------------------------------
# Secrets Manager
#----------------------------------------

# Anthropic API Key
resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/anthropic-api-key"
  description = "Anthropic API Key for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-anthropic-key" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "anthropic_api_key" {
  secret_id     = aws_secretsmanager_secret.anthropic_api_key.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Azure OpenAI API Key
resource "aws_secretsmanager_secret" "azure_openai_api_key" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/azure-openai-api-key"
  description = "Azure OpenAI API Key for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-azure-openai-key" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "azure_openai_api_key" {
  secret_id     = aws_secretsmanager_secret.azure_openai_api_key.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Azure OpenAI Endpoint
resource "aws_secretsmanager_secret" "azure_openai_endpoint" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/azure-openai-endpoint"
  description = "Azure OpenAI Endpoint for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-azure-openai-endpoint" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "azure_openai_endpoint" {
  secret_id     = aws_secretsmanager_secret.azure_openai_endpoint.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Azure OpenAI Deployment Name
resource "aws_secretsmanager_secret" "azure_openai_deployment_name" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/azure-openai-deployment-name"
  description = "Azure OpenAI Deployment Name for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-azure-openai-deployment" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "azure_openai_deployment_name" {
  secret_id     = aws_secretsmanager_secret.azure_openai_deployment_name.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Azure OpenAI API Version
resource "aws_secretsmanager_secret" "azure_openai_api_version" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/azure-openai-api-version"
  description = "Azure OpenAI API Version for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-azure-openai-version" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "azure_openai_api_version" {
  secret_id     = aws_secretsmanager_secret.azure_openai_api_version.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Innography Username
resource "aws_secretsmanager_secret" "innography_user_name" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/innography-user-name"
  description = "Innography Username for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-innography-username" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "innography_user_name" {
  secret_id     = aws_secretsmanager_secret.innography_user_name.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Innography User Secret
resource "aws_secretsmanager_secret" "innography_user_secret" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/innography-user-secret"
  description = "Innography User Secret for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-innography-secret" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "innography_user_secret" {
  secret_id     = aws_secretsmanager_secret.innography_user_secret.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Innography User Token
resource "aws_secretsmanager_secret" "innography_user_token" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/innography-user-token"
  description = "Innography User Token for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-innography-token" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "innography_user_token" {
  secret_id     = aws_secretsmanager_secret.innography_user_token.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Innography Token URL
resource "aws_secretsmanager_secret" "innography_token_url" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/innography-token-url"
  description = "Innography Token URL for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-innography-token-url" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "innography_token_url" {
  secret_id     = aws_secretsmanager_secret.innography_token_url.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Innography Services URL
resource "aws_secretsmanager_secret" "innography_services_url" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/innography-services-url"
  description = "Innography Services URL for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-innography-services-url" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "innography_services_url" {
  secret_id     = aws_secretsmanager_secret.innography_services_url.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Derwent API Base URL
resource "aws_secretsmanager_secret" "derwent_api_base_url" {
  name        = "/${var.app_family}/${var.app_name}/${var.env_name}/derwent-api-base-url"
  description = "Derwent API Base URL for ${var.app_name}"

  tags = merge(
    local.common_tags,
    { "Name" = "${local.long_service_name}-derwent-api-base-url" },
    { "tr:role" = "secret" }
  )
}

resource "aws_secretsmanager_secret_version" "derwent_api_base_url" {
  secret_id     = aws_secretsmanager_secret.derwent_api_base_url.id
  secret_string = "PLACEHOLDER_VALUE_SET_IN_AWS_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
