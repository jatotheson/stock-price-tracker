import os
import json
from datetime import datetime, timezone

import boto3


ecs = boto3.client("ecs")
sns = boto3.client("sns")

CLUSTER = os.environ["ECS_CLUSTER"]
SERVICE = os.environ["ECS_SERVICE"]
TOPIC_ARN = os.environ.get("NOTIFY_TOPIC_ARN")


def publish_notification(action: str, desired: int, source: str) -> None:
    if not TOPIC_ARN:
        return

    ts = datetime.now(timezone.utc).isoformat()

    subject = f"Stock worker turned {action.upper()}"
    message = {
        "action": action,
        "desiredCount": desired,
        "source": source,
        "cluster": CLUSTER,
        "service": SERVICE,
        "timestamp": ts,
    }

    try:
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject=subject,  # used for email; ignored for SMS
            Message=json.dumps(message, default=str),
        )
    except Exception as e:
        # Don't break the main logic just because SNS failed
        print(f"[WARN] Failed to publish SNS notification: {e}", flush=True)


def handler(event, context):
    # Determine source: scheduler vs API
    source = "api"
    if event.get("source") == "aws.scheduler":
        source = "scheduler"

    action = None
    body = {}

    # 1) API Gateway: JSON body
    if event.get("body"):
        try:
            body = json.loads(event["body"])
            action = body.get("action")
        except Exception:
            pass

    # 2) API Gateway: query string ?action=on
    if not action:
        qs = event.get("queryStringParameters") or {}
        action = qs.get("action")

    # 3) EventBridge Scheduler: top-level "action"
    if not action:
        action = event.get("action")

    if action not in ("on", "off"):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "action must be 'on' or 'off'"})
        }

    desired = 1 if action == "on" else 0

    ecs.update_service(
        cluster=CLUSTER,
        service=SERVICE,
        desiredCount=desired,
    )

    publish_notification(action, desired, source)

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok", "desiredCount": desired})
    }
