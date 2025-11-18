import os
import json
import boto3

ecs = boto3.client("ecs")

CLUSTER = os.environ["ECS_CLUSTER"]
SERVICE = os.environ["ECS_SERVICE"]


def handler(event, context):
    # Event can come from:
    # - API Gateway HTTP API (body JSON or ?action=)
    # - EventBridge Scheduler ({ "action": "on" } / { "action": "off" })

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

    action = None if type(action) != str else action.lower()
    if action not in ("on", "off"):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "action must be 'on' or 'off'"})
        }

    desired = 1 if action == "on" else 0

    ecs.update_service(
        cluster=CLUSTER,
        service=SERVICE,
        desiredCount=desired
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok", "desiredCount": desired})
    }
