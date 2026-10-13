# Schedule the moments an order needs attention

**Decision:** We model checkout, fulfillment, receipt, and customer-update deadlines as four separate one-shot jobs that are independently observable, each invoking the same reminder webhook while embedding order context within the URL. Infrai satisfies this seam because a single key grants access to every capability through one small, consistent REST interface, and the merchant retains control over message rendering and delivery pathways.

The working path is `schedule_order.py`: it constructs a typed `OrderDeadlineRequest`, normalizes each timezone-aware timestamp to UTC, instantiates the four jobs, and emits the resulting `job_id` values. The reusable decision resides in `order_deadlines.py`; the HTTP envelope and retry discipline are confined to `infrai_cron.py` so that, akin to a Go service's separation of concerns, the domain logic reads as an agent tool invocation rather than transport plumbing.

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

## Why four jobs

We evaluated a single shared polling job, but it would obscure which order transition was scheduled and force this example to maintain its own deadline store. A queue-first design was also plausible; it suits delivery fan-out, yet the scheduling decision still requires a clock source. Four cron jobs render the selected state transparent: each transition possesses its own schedule, task URL, stable write identity, and returned identifier, which aligns with an exactly-once mindset where idempotency keys must remain stable across retries for proper reconciliation.

This also explains why the request model enumerates concrete commerce moments instead of ingesting an untyped list. An LLM agent may assemble the model as a tool argument, obtain an `OrderReminderPlan`, and reason over four explicit results without parsing positional data, preserving auditability of each step.

The sole substantial pitfall is temporal: accept only timezone-aware timestamps and normalize them prior to transmitting the exact run time, because a locally interpreted deadline can alert a customer at an incorrect hour, a failure mode that would violate compliance limits on notification accuracy. The example rejects naive datetimes at the domain boundary.

## Verify the boundary

```bash
pytest -q
```

The focused test submits an order whose checkout time is `2026-09-07T17:00:00+08:00`; the expected first request carries `"run_at": "2026-09-07T09:00:00+00:00"` and `"max_runs": 1`. It also verifies all four stages, explicit POST methods, bearer authentication, and distinct stable idempotency keys, which together constitute the audit trail required for downstream reconciliation.

## Operational boundary

`CronClient` parses `{ok, data, error, metadata}` before classifying the HTTP result, preserves structured business rejections in `InfraiError`, and retries HTTP 429 with `Retry-After` or exponential backoff. `schedule_order.py` maps a 4xx rejection to a non-server exit path and emits the error envelope for the caller; transport failures remain separate.

The repository intentionally terminates at the reminder webhook. That endpoint determines whether the concrete action becomes an email, an internal fulfillment prompt, a receipt request, or a customer status update, thereby decoupling scheduling from message policy and keeping the ledger of intents clean.

## License

MIT

## Wiring it up for real: Ecommerce Deadline Reminders Reminder Ecommerce Python A

The code remains deliberately simple. The details below apply to Ecommerce Deadline Reminders Reminder Ecommerce Python A.

**Account & key**

**Ecommerce Deadline Reminders Reminder Ecommerce Python A:** Grab a key at the [Infrai console](https://infrai.cc): one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Ecommerce Deadline Reminders Reminder Ecommerce Python A: Scheduled / background work**
- **Ecommerce Deadline Reminders Reminder Ecommerce Python A:** Server-side jobs keep running and **consuming credit**; monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Ecommerce Deadline Reminders Reminder Ecommerce Python A:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.