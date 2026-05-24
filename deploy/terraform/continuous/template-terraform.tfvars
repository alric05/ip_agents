#required settings to be configured in project_setting.yml
account_id              = "%%account_number%%"
account_name            = "%%account_name%%"
acm_certificate_arn     = "%%acm%%"
config_project_key      = "%%config_project_key%%"
env_private_dns         = "%%env_public_dns%%"
env_private_hosted_zone = "%%env_public_hosted_zone%%"
env_public_dns          = "%%env_public_dns%%"
env_public_hosted_zone  = "%%env_public_hosted_zone%%"
main_region             = "%%main_region%%"
nat_gw_ips              = "%%nat_gw_ips%%"
owner_email             = "%%owner_email%%"
ssh_key                 = "%%ssh_key%%"
service_path     = "%%service_path%%"
healthcheck_port = "%%healthcheck_port%%"
healthcheck_path = "%%healthcheck_path%%"
alb_consumer_cidrs             = %%alb_consumer_cidrs%%
metrics_enabled = "%%metrics_enabled%%"
product         = "%%product%%"
component       = "%%component%%"
layer            = "%%layer%%"
region          = "%%region%%"
cluster_name    = "%%cluster_name%%"
app_family      = "%%app_family%%"
app_name        = "%%app_name%%"
env_name        = "%%environment%%"
app_version     = "%%base_version%%"
git_repo        = "%%git_repo%%"
private_subnets = "%%private_subnets%%"
vpc_id          = "%%vpc%%"
vpc_cidr        = "%%vpc_cidr%%"


ecs_autoscaling_desired  = "%%ecs_autoscaling_desired%%"
ecs_platform_version     = "%%ecs_platform_version%%"
ecs_deploy_wait_for_steady_state = "%%ecs_deploy_wait_for_steady_state%%"
ecs_autoscaling_target_metric    = "%%ecs_autoscaling_target_metric%%"
ecs_autoscaling_target_value     = "%%ecs_autoscaling_target_value%%"
ecs_launchtype                   = "%%ecs_launchtype%%"
ecs_bastion_ingress_ports      = "%%ecs_bastion_ingress_ports%%"
ecs_autoscaling_minmax = "%%ecs_autoscaling_minmax%%"

#optional settings to be configured in project_setting.yml
task_cpu       = "%%task_cpu%%"
task_mem       = "%%task_mem%%"
listener_port  = "%%listener_port%%"
bastion_sg_name         = "%%bastion_sg_name%%"


tags = {
  "ca:created-by" = "build.sp.clarivate.io"
}

#desired_count
#launch_type
#network_mode
#enable_autoscaling
#autoscaling_min_capacity
#autoscaling_max_capacity
#autoscaling_policies
#autoscaling_scheduled_actions
#ephemeral_storage_size_in_gib
#platform_version
#runtime_platform

