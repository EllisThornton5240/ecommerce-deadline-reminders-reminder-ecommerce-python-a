"""Turn an order's four deadlines into observable reminder cron jobs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import urlencode, urlsplit, urlunsplit

from infrai_cron import CronClient


class ReminderKind(str, Enum):
    CHECKOUT = "checkout"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    CUSTOMER_UPDATE = "customer_update"


@dataclass(frozen=True)
class OrderDeadlineRequest:
    order_id: str
    checkout_due_at: datetime
    fulfillment_due_at: datetime
    receipt_due_at: datetime
    customer_update_due_at: datetime
    reminder_webhook_url: str


@dataclass(frozen=True)
class ScheduledReminder:
    kind: ReminderKind
    due_at: datetime
    job_id: str


@dataclass(frozen=True)
class OrderReminderPlan:
    order_id: str
    reminders: tuple[ScheduledReminder, ...]


class OrderReminderService:
    def __init__(self, cron: CronClient) -> None:
        self.cron = cron

    def schedule(self, request: OrderDeadlineRequest) -> OrderReminderPlan:
        deadlines = (
            (ReminderKind.CHECKOUT, request.checkout_due_at),
            (ReminderKind.FULFILLMENT, request.fulfillment_due_at),
            (ReminderKind.RECEIPT, request.receipt_due_at),
            (ReminderKind.CUSTOMER_UPDATE, request.customer_update_due_at),
        )
        scheduled = []
        for kind, due_at in deadlines:
            utc_due_at = _as_utc(due_at)
            job = self.cron.create(
                run_at=utc_due_at.isoformat(),
                task=_task_url(request.reminder_webhook_url, request.order_id, kind),
                max_runs=1,
                idempotency_key=_idempotency_key(request.order_id, kind, utc_due_at),
            )
            scheduled.append(ScheduledReminder(kind, utc_due_at, job.job_id))
        return OrderReminderPlan(request.order_id, tuple(scheduled))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("deadline timestamps must include a timezone")
    return value.astimezone(timezone.utc)

def _task_url(base_url: str, order_id: str, kind: ReminderKind) -> str:
    parts = urlsplit(base_url)
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError("reminder_webhook_url must be an absolute HTTPS URL")
    query = urlencode({"order_id": order_id, "reminder": kind.value})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _idempotency_key(order_id: str, kind: ReminderKind, due_at: datetime) -> str:
    identity = f"{order_id}:{kind.value}:{due_at.isoformat()}"
    return "order-reminder-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
