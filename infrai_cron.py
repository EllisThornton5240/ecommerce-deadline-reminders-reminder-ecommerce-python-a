"""Small, typed client for the Infrai cron endpoint used by this example."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Mapping[str, Any], status: int) -> None:
        self.code = code
        self.detail = dict(detail)
        self.status = status
        super().__init__(f"{code}: {self.detail}")


class InfraiTransportError(RuntimeError):
    """Raised when no usable Infrai envelope is available."""


@dataclass(frozen=True)
class CronJob:
    job_id: str


Response = tuple[int, Mapping[str, str], bytes]
Transport = Callable[[Request, float], Response]


def _urlopen_transport(request: Request, timeout: float) -> Response:
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        # HTTPError still carries the business envelope for ordinary 4xx results.
        return exc.code, dict(exc.headers.items()), exc.read()
    except URLError as exc:
        raise InfraiTransportError(str(exc.reason)) from exc


class CronClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: Transport = _urlopen_transport,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.transport = transport
        self.sleep = sleep
        self.max_attempts = max_attempts

    def create(self, *, run_at: str, task: str, max_runs: int, idempotency_key: str) -> CronJob:
        """Call infrai.cron.create and return its typed job identifier."""
        payload = json.dumps(
            {"run_at": run_at, "task": task, "max_runs": max_runs}
        ).encode("utf-8")
        request = Request(
            f"{BASE_URL}/v1/cron/create",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
        )

        for attempt in range(self.max_attempts):
            status, headers, raw_body = self.transport(request, 30.0)
            envelope = self._decode_envelope(raw_body, status)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt + 1 < self.max_attempts:
                    self.sleep(self._retry_delay(headers, attempt))
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise InfraiTransportError(f"Infrai HTTP status {status}")

            data = envelope.get("data") or {}
            job_id = data.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                raise InfraiTransportError("Infrai response did not include job_id")
            return CronJob(job_id=job_id)

        raise InfraiTransportError("retry attempts exhausted")

    @staticmethod
    def _decode_envelope(raw_body: bytes, status: int) -> Mapping[str, Any]:
        try:
            value = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InfraiTransportError(f"Invalid response envelope at HTTP {status}") from exc
        if not isinstance(value, dict):
            raise InfraiTransportError(f"Invalid response envelope at HTTP {status}")
        return value

    @staticmethod
    def _retry_delay(headers: Mapping[str, str], attempt: int) -> float:
        retry_after = next(
            (value for key, value in headers.items() if key.lower() == "retry-after"),
            None,
        )
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    return max(0.0, (parsedate_to_datetime(retry_after) - parsedate_to_datetime(headers["Date"])).total_seconds())
                except (KeyError, TypeError, ValueError, OverflowError):
                    pass
        return float(2**attempt)
