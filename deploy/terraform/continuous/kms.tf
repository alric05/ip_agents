#----------------------------------------
# KMS Key
#----------------------------------------
resource "aws_kms_alias" "kms_key_alias" {
    name          = "alias/${local.long_service_name}-key"
    target_key_id = "${aws_kms_key.kms_key.key_id}"
}

resource "aws_kms_key" "kms_key" {
    description             = "${local.long_service_name} Key"
    deletion_window_in_days = 30
    enable_key_rotation     = true

    tags = merge(
        local.common_tags,
        { "Name" = "${local.long_service_name}" },
        { "tr:role" = "kms" },
    )

    policy                  = jsonencode(
        {
            "Version": "2012-10-17",
            "Id": "IAM specific Policy",
            "Statement": [
                {
                    "Sid": "Enable Specific IAM Role Full Permissions",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": [
                            "${local.major_env != "prod" ? "*" : "arn:aws:iam::649280551980:role/aws-reserved/sso.amazonaws.com/us-west-2/AWSReservedSSO_clarivate_superadmin_8d3a2fa95b80b44f"}",
                            "arn:aws:iam::${var.account_id}:role/cl/app/crossaccount/sp-jenkins-deploy"
                        ]
                    },
                    "Action": "kms:*",
                    "Resource": "*"
                },
                {
                    "Sid": "Enable Specific IAM Role encrypt and decrypt Permissions",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": [
                            "${aws_iam_role.ecs_container_role.arn}"
                        ]
                    },
                    "Action": [
                        "kms:DescribeKey",
                        "kms:GenerateDataKey*",
                        "kms:Encrypt",
                        "kms:ReEncrypt*",
                        "kms:Decrypt"
                    ],
                    "Resource": "*"
                }
            ]
        }
    )
}
