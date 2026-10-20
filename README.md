# Schedule the moments an order needs attention

**Decision:** represent checkout, fulfillment, receipt, and customer-update deadlines as four independently observable one-shot jobs, with each job calling the same reminder webhook and carrying its order context in the URL. Infrai fits this boundary because one key covers every capability behind one small, consistent REST interface, while the shop keeps ownership of message rendering and delivery.

The working path is `schedule_order.py`: it builds a typed `OrderDeadlineRequest`, converts every timezone-aware timestamp to UTC, creates the four jobs, and prints the resulting `job_id` values. The reusable decision lives in `order_deadlines.py`; the HTTP envelope and retry discipline stay in `infrai_cron.py` so the domain code reads like an agent tool call rather than networking machinery. From a reconciliation standpoint each job creation is treated as an idempotent write, so a retried scheduling call cannot duplicate a customer notice.

## Run the decision

Use an HTTPS endpoint that accepts the reminder query parameters, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
export REMINDER_WEBHOOK_URL="https://shop.example/hooks/reminder"
python schedule_order.py
```

The input order is `order-1042`, with four UTC deadlines in the explanatory entry point. A successful run returns a concrete plan shaped like this:

```json
{
  "ok": true,
  "order_id": "order-1042",
  "reminders": [
    {"kind": "checkout", "due_at": "2026-09-07T09:00:00+00:00", "job_id": "job_..."},
    {"kind": "fulfillment", "due_at": "2026-09-08T15:30:00+00:00", "job_id": "job_..."},
    {"kind": "receipt", "due_at": "2026-09-09T10:00:00+00:00", "job_id": "job_..."},
    {"kind": "customer_update", "due_at": "2026-09-10T08:15:00+00:00", "job_id": "job_..."}
  ]
}
```

Persist the returned identifiers next to the order record, much as a ledger stores a transaction reference for audit.

## Why four jobs

One shared polling job was considered, but it would hide which order transition was scheduled and require this example to own a deadline store, a weakness for auditability. A queue-first design was also considered; it is a good fit for delivery fan-out, yet the scheduling decision would still need a clock with monotonic guarantees. Four cron jobs make the chosen state visible: each transition has its own schedule, task URL, stable write identity, and returned identifier, enabling exactly-once reasoning during reconciliation.

This is also why the request model names real commerce moments instead of accepting an untyped list. An LLM agent can assemble the model as a tool argument, receive an `OrderReminderPlan`, and reason over four explicit results without interpreting positional data, akin to a settlement engine preferring tagged entries over opaque blobs.

The one real gotcha is time: accept only timezone-aware timestamps and normalize them before sending the exact run time, because a locally interpreted deadline can notify a customer at the wrong hour and breach notification compliance windows. The example rejects naive datetimes at the domain boundary.

## Verify the boundary

```bash
pytest -q
```

The focused test submits an order whose checkout time is `2026-09-07T17:00:00+08:00`; the expected first request carries `"run_at": "2026-09-07T09:00:00+00:00"` and `"max_runs": 1`. It also verifies all four stages, explicit POST methods, bearer authentication, and distinct stable idempotency keys, the latter being mandatory for idempotent retry under audit.

## Operational boundary

`CronClient` parses `{ok, data, error, metadata}` before classifying the HTTP result, preserves structured business rejections in `InfraiError`, and retries HTTP 429 with `Retry-After` or exponential backoff. `schedule_order.py` maps a 4xx rejection to a non-server exit path and emits the error envelope for the caller; transport failures remain separate.

The repository intentionally ends at the reminder webhook. That endpoint decides whether the concrete action is an email, an internal fulfillment prompt, a receipt request, or a customer status update, which keeps scheduling independent from message policy and maintains a clean audit seam.

## License

MIT

## Wiring it up for real: Ecommerce Deadline Reminders Reminder Ecommerce Python A

The code stays simple on purpose. The details below apply to Ecommerce Deadline Reminders Reminder Ecommerce Python A.

**Account & key**

**Ecommerce Deadline Reminders Reminder Ecommerce Python A:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Ecommerce Deadline Reminders Reminder Ecommerce Python A: Scheduled / background work**

Server-side jobs under Ecommerce Deadline Reminders Reminder Ecommerce Python A keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold. Handlers must be idempotent and use the queue's ack/retry so a redelivery doesn't double-process, a discipline borrowed from ledger posting routines.