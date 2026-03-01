import base64
import json
import os
import urllib.request

SLACK_WEBHOOK = os.environ["SLACK_WEBHOOK"]


def notify_slack(event, context):
    data = json.loads(base64.b64decode(event["data"]).decode())

    # Only notify when a budget threshold is actually crossed, not on every cost update.
    if "alertThresholdExceeded" not in data:
        return

    cost = data.get("costAmount", "?")
    budget = data.get("budgetAmount", "?")
    name = data.get("budgetDisplayName", "Budget")
    currency = data.get("currencyCode", "USD")
    threshold = data["alertThresholdExceeded"]

    text = f":information_source: *{name}*: ${cost} / ${budget} {currency} — reached {round(threshold * 100)}% of budget"

    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)
