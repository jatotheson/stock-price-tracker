############################
# ECR repository
############################

resource "aws_ecr_repository" "worker" {
    name = "${var.project_name}-worker"

    image_scanning_configuration {
        scan_on_push = true
    }

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

############################
# IAM role for ECS task
############################

data "aws_iam_policy_document" "ecs_task_assume" {
    statement {
        actions = ["sts:AssumeRole"]

        principals {
            type        = "Service"
            identifiers = ["ecs-tasks.amazonaws.com"]
        }
    }
}

resource "aws_iam_role" "ecs_task_role" {
    name                 = "${var.project_name}-ecs-task-role-${var.env}"
    assume_role_policy   = data.aws_iam_policy_document.ecs_task_assume.json

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

# Allow ECS task to pull from ECR and write logs (standard managed policy)
resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
    role         = aws_iam_role.ecs_task_role.name
    policy_arn   = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Custom inline policy to allow the task to write stock data to your S3 bucket
resource "aws_iam_role_policy" "ecs_task_s3_policy" {
    name = "${var.project_name}-ecs-task-s3-policy-${var.env}"
    role = aws_iam_role.ecs_task_role.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Action = [
                  "s3:PutObject",
                  "s3:AbortMultipartUpload",
                  "s3:ListBucket"
                ]
                Resource = [
                  aws_s3_bucket.stock_data.arn,
                  "${aws_s3_bucket.stock_data.arn}/*"
                ]
            }
        ]
    })
}


############################
# DynamoDB permissions for ECS task
############################

resource "aws_iam_role_policy" "ecs_task_ddb_policy" {
    name = "${var.project_name}-ecs-task-ddb-policy-${var.env}"
    role = aws_iam_role.ecs_task_role.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Action = [
                    "dynamodb:PutItem",
                    "dynamodb:DescribeTable"
                ]
                Resource = aws_dynamodb_table.intraday.arn
            }
        ]
    })
}


############################
# CloudWatch Logs
############################

resource "aws_cloudwatch_log_group" "worker" {
    name                    = "/ecs/${var.project_name}-worker-${var.env}"
    retention_in_days   = 7

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

############################
# Networking (use default VPC)
############################

data "aws_vpc" "default" {
    default = true
}

data "aws_subnets" "default" {
    filter {
        name   = "vpc-id"
        values = [data.aws_vpc.default.id]
    }
}

resource "aws_security_group" "worker_sg" {
    name            = "${var.project_name}-worker-sg-${var.env}"
    description   = "Security group for ECS worker tasks"
    vpc_id        = data.aws_vpc.default.id

    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

############################
# ECS Cluster
############################

resource "aws_ecs_cluster" "this" {
    name = "${var.project_name}-cluster-${var.env}"

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

############################
# ECS Task Definition (Fargate)
############################

resource "aws_ecs_task_definition" "worker" {
    family                         = "${var.project_name}-worker-${var.env}"
    cpu                            = "256"
    memory                         = "512"
    network_mode                   = "awsvpc"
    requires_compatibilities       = ["FARGATE"]
    execution_role_arn             = aws_iam_role.ecs_task_role.arn
    task_role_arn                  = aws_iam_role.ecs_task_role.arn

    runtime_platform {
        cpu_architecture        = "ARM64"
        operating_system_family = "LINUX"
    }

    container_definitions = jsonencode([
        {
            name        = "worker"
            image       = "${aws_ecr_repository.worker.repository_url}:latest"
            essential   = true
            environment = [
                {
                    name  = "S3_BUCKET"
                    value = aws_s3_bucket.stock_data.bucket
                },
                {
                    name  = "STOCK_LIST"
                    value = join(",", var.stock_symbols)
                },
                {
                    name  = "DDB_INTRADAY_TABLE"
                    value = aws_dynamodb_table.intraday.name
                },
                {
                    name  = "INTRADAY_TTL_DAYS"
                    value = "60"
                }
            ]
            logConfiguration = {
                logDriver = "awslogs"
                options = {
                  awslogs-group         = aws_cloudwatch_log_group.worker.name
                  awslogs-region        = var.aws_region
                  awslogs-stream-prefix = "ecs"
                }
            }
        }
    ])

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}

############################
# ECS Service (Fargate)
############################

resource "aws_ecs_service" "worker" {
    name            = "${var.project_name}-worker-service-${var.env}"
    cluster         = aws_ecs_cluster.this.id
    task_definition = aws_ecs_task_definition.worker.arn
    desired_count   = 0         # start OFF by default
    launch_type     = "FARGATE"

    network_configuration {
        assign_public_ip = true
        subnets          = data.aws_subnets.default.ids
        security_groups  = [aws_security_group.worker_sg.id]
    }

    lifecycle {
        ignore_changes = [desired_count] # we'll control this via Lambda/EventBridge later
    }

    tags = {
        Project = var.project_name
        Env     = var.env
    }
}


