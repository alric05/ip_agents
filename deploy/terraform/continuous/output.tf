
output "ecs_task_arn" {
    value = aws_ecs_task_definition.ecs_task.arn
}

output "ecs_service_arn" {
    value = aws_ecs_service.ecs_service.id
}

output "application_url" {
    value = "https://${aws_route53_record.ecs_load_balancer.name}${var.service_path}"
}

output "application_healthcheck_url" {
    value = "https://${aws_route53_record.ecs_load_balancer.name}${var.healthcheck_path}"
}