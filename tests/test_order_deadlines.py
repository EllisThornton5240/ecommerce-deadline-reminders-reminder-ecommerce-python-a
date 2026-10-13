from __future__ import annotations

import json
from datetime import datetime
from urllib.request import Request

from infrai_cron import CronClient
from order_deadlines import OrderDeadlineRequest, OrderReminderService


def test_schedules_each_order_transition_with_stable_write_identity() -> None:
    calls: list[tuple[Request, float]] = []

    def transport(request: Request, timeout: float):
        calls.append((request, timeout))
        body = json.dumps({"ok": True, "data": {"job_id": f"job-{len(calls)}"}, "error": None, "metadata": {}})
        return 200, {}, body.encode("utf-8")

    request = OrderDeadlineRequest(
        order_id="order-1042",
        checkout_due_at=datetime.fromisoformat("2026-09-07T17:00:00+08:00"),
        fulfillment_due_at=datetime.fromisoformat("2026-09-08T15:30:00+00:00"),
        receipt_due_at=datetime.fromisoformat("2026-09-09T10:00:00+00:00"),
        customer_update_due_at=datetime.fromisoformat("2026-09-10T08:15:00+00:00"),
        reminder_webhook_url="https://shop.example/hooks/reminder",
    )

    plan = OrderReminderService(CronClient("test-key", transport=transport)).schedule(request)

    assert [item.kind.value for item in plan.reminders] == [
        "checkout", "fulfillment", "receipt", "customer_update"
    ]
    assert [item.job_id for item in plan.reminders] == ["job-1", "job-2", "job-3", "job-4"]
    sent = [json.loads(call[0].data or b"") for call in calls]
    assert sent[0] == {
        "run_at": "2026-09-07T09:00:00+00:00",
        "task": "https://shop.example/hooks/reminder?order_id=order-1042&reminder=checkout",
        "max_runs": 1,
    }
    assert sent[3]["run_at"] == "2026-09-10T08:15:00+00:00"
    assert all(payload["max_runs"] == 1 for payload in sent)
    assert all(call[0].method == "POST" for call in calls)
    assert all(call[0].get_header("Authorization") == "Bearer test-key" for call in calls)
    keys = [call[0].get_header("Idempotency-key") for call in calls]
    assert len(set(keys)) == 4
