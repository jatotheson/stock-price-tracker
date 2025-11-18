import os
import json
import boto3

ecs = boto3.client("ecs")

CLUSTER = os.environ["ECS_CLUSTER"]
SERVICE = os.environ["ECS_SERVICE"]

'''
POST /worker with body { "action": "on" } or { "action": "off" }
(or ?action=on / ?action=off).
'''
def handler(event, context):
    # Try body first
    action = None
    body = {}

    if event.get("body"):
        try:
            body = json.loads(event["body"])
            action = body.get("action")
        except Exception:
            pass

    # Fallback: query string ?action=on/off
    if not action:
        qs = event.get("queryStringParameters") or {}
        action = qs.get("action")

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

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok", "desiredCount": desired})
    }
