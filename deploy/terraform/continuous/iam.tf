#----------------------------------------
# Common ECS Task/Service role/policies
#----------------------------------------
resource "aws_iam_role" "ecs_container_role" {
    name = "ecs-${local.long_service_name}-role"
    path = "/cl/app/${var.app_family}/"
    assume_role_policy = jsonencode(
        {
            "Version" : "2012-10-17",
            "Statement" : [
                {
                    "Effect" : "Allow",
                    "Principal" : {
                        "Service" : [
                            "ecs-tasks.amazonaws.com",
                            "ecs.amazonaws.com",
                            "ec2.amazonaws.com"
                        ]
                    },
                    "Action" : "sts:AssumeRole"
                }
            ]
        }
    )

    tags = (merge(
        local.common_tags,
        { "Name" = "${var.app_family}-${var.app_name}-${var.env_name}" },
        { "tr:role" = "iam" },
    ))

}

# common ecs task role policies
resource "aws_iam_policy" "ecs_container_role_policy" {
    name        = "ecs-${local.long_service_name}-role-policy"
    path        = "/cl/app/${var.app_family}/"
    description = "ECS Run Task Policy"
    policy = jsonencode(
        {
            "Version" : "2012-10-17",
            "Statement" : [
                {
                    "Effect" : "Allow",
                    "Action" : [
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "logs:DescribeLogStreams",
                        "logs:DescribeLogGroups",
                        "logs:PutLogEvents",
                        "ssmmessages:CreateControlChannel",
                        "ssmmessages:CreateDataChannel",
                        "ssmmessages:OpenControlChannel",
                        "ssmmessages:OpenDataChannel",
                        "ssm:Describe*",
                        "ssm:Get*",
                        "ssm:List*",
                        "secretsmanager:Get*",
                        "secretsmanager:Describe*",
                        "secretsmanager:List*",
                        "kms:Describe*",
                        "kms:Get*",
                        "kms:List*",
                        "ses:*"
                    ],
                    "Resource" : "*"
                },
                {
                    "Effect" : "Allow",
                    "Action" : [
                        "secretsmanager:Describe*",
                        "secretsmanager:Get*",
                        "secretsmanager:List*"
                    ],
                    "Resource" : [
                        "arn:aws:secretsmanager:${var.region}:761762634378:secret:/${var.app_family}/common/rds/${var.env_name}/app*"
                    ]
                },
                {
                    "Effect" : "Allow",
                    "Action" : [
                        "ecs:CreateCluster",
                        "ecs:DeregisterContainerInstance",
                        "ecs:DiscoverPollEndpoint",
                        "ecs:Poll",
                        "ecs:RegisterContainerInstance",
                        "ecs:StartTelemetrySession",
                        "ecs:Submit*",
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecs:StartTask"
                    ],
                    "Resource" : "*"
                },
                {
                    "Effect" : "Allow",
                    "Action" : [
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                        "xray:GetSamplingStatisticSummaries",
                        "cloudwatch:PutMetricData",
                        "ecs:ListTasks",
                        "ecs:ListServices",
                        "ecs:DescribeContainerInstances",
                        "ecs:DescribeServices",
                        "ecs:DescribeTasks",
                        "ecs:DescribeTaskDefinition",
                        "ecs:DescribeInstances"
                    ],
                    "Resource" : ["*"]
                },
            ]
        }
    )
}

resource "aws_iam_role_policy_attachment" "ecs_container_role_policy_attachment" {
    role       = aws_iam_role.ecs_container_role.name
    policy_arn = aws_iam_policy.ecs_container_role_policy.arn
}