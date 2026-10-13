"""Explanatory entry point: schedule one order's customer-facing deadlines."""

from __future__ import annotations

import json
import os
from datetime import datetime

from infrai_cron import CronClient, InfraiError, InfraiTransportError
from order_deadlines import OrderDeadlineRequest, OrderReminderService


def main() -> int:
    request = OrderDeadlineRequest(
        order_id=os.environ.get("ORDER_ID", "order-1042"),
        checkout_due_at=datetime.fromisoformat("2026-09-07T09:00:00+00:00"),
        fulfillment_due_at=datetime.fromisoformat("2026-09-08T15:30:00+00:00"),
        receipt_due_at=datetime.fromisoformat("2026-09-09T10:00:00+00:00"),
        customer_update_due_at=datetime.fromisoformat("2026-09-10T08:15:00+00:00"),
        reminder_webhook_url=os.environ["REMINDER_WEBHOOK_URL"],
    )
    try:
        plan = OrderReminderService(CronClient()).schedule(request)
    except InfraiError as exc:
        print(json.dumps({"ok": False, "status": exc.status, "error": exc.detail}))
        return 2 if 400 <= exc.status < 500 else 1
    except InfraiTransportError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "order_id": plan.order_id,
                "reminders": [
                    {"kind": item.kind.value, "due_at": item.due_at.isoformat(), "job_id": item.job_id}
                    for item in plan.reminders
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
