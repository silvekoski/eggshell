"""A small client for NVIDIA Nemotron 3.5 Super VL (OpenAI-compatible API).

Standard library only (urllib), so the teleop install needs no new package.
It is never called from the control loop: only from `teleop review`, after
the episodes are saved.

- Key: env NVIDIA_API_KEY. With no key, `configured()` is False and callers
  show "Nemotron not configured" and skip the step.
- Retries with exponential backoff on 429, 5xx and network errors.
- Timeout per request (60 s by default).
- Responses are cached on disk by the hash of the request body, so a second
  `teleop review` over the same episodes costs no requests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
DISPLAY_NAME = "Nemotron 3.5 Super VL"
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class NemotronError(RuntimeError):
    pass


class NemotronNotConfigured(NemotronError):
    pass


def image_part(png_bytes: bytes) -> dict:
    return {"type": "image_url",
            "image_url": {"url": "data:image/png;base64," + base64.b64encode(png_bytes).decode()}}


# (url, body bytes, headers, timeout) -> (status, response bytes). Tests replace it.
Transport = Callable[[str, bytes, dict, float], tuple[int, bytes]]


def _urllib_transport(url: str, body: bytes, headers: dict, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https base URL)
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


@dataclass
class NemotronClient:
    api_key: str | None = field(default_factory=lambda: os.environ.get("NVIDIA_API_KEY") or None)
    base_url: str = field(default_factory=lambda: os.environ.get("NEMOTRON_BASE_URL") or DEFAULT_BASE_URL)
    model: str = field(default_factory=lambda: os.environ.get("NEMOTRON_MODEL") or DEFAULT_MODEL)
    timeout_s: float = 60.0
    max_retries: int = 4
    backoff_s: float = 2.0
    cache_dir: Path | None = None
    transport: Transport = _urllib_transport
    sleep: Callable[[float], None] = time.sleep
    requests_made: int = 0
    cache_hits: int = 0

    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 4096) -> str:
        """One chat completion. Returns the assistant text."""
        if not self.configured():
            raise NemotronNotConfigured("Nemotron not configured: set NVIDIA_API_KEY")
        payload = {"model": self.model, "messages": messages, "temperature": temperature,
                   "max_tokens": max_tokens}
        body = json.dumps(payload, sort_keys=True).encode()
        key = hashlib.sha256(body).hexdigest()
        cached = self._cache_get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   "Accept": "application/json"}
        last = ""
        for attempt in range(self.max_retries + 1):
            try:
                self.requests_made += 1
                status, raw = self.transport(url, body, headers, self.timeout_s)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                status, raw, last = 0, b"", f"network error: {e}"
            if status == 200:
                text, finish = _extract_text(raw)
                if text.strip():
                    self._cache_put(key, text)  # never cache an empty reply
                elif finish == "length":
                    # A reasoning model can spend the whole budget thinking and
                    # return no content. Say so, so the repair request is clear.
                    text = f"(empty reply: the {max_tokens}-token budget ran out during reasoning)"
                return text
            if status:
                last = f"HTTP {status}: {raw[:300].decode(errors='replace')}"
            if status and status not in RETRY_STATUS:
                break
            if attempt < self.max_retries:
                self.sleep(self.backoff_s * (2 ** attempt) * (0.75 + 0.5 * random.random()))
        raise NemotronError(f"Nemotron unavailable after {self.requests_made} request(s): {last}")

    def _cache_get(self, key: str) -> str | None:
        if self.cache_dir is None:
            return None
        p = self.cache_dir / f"{key}.json"
        return json.loads(p.read_text())["text"] if p.exists() else None

    def _cache_put(self, key: str, text: str) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / f"{key}.json").write_text(json.dumps({"model": self.model, "text": text}))


def _extract_text(raw: bytes) -> tuple[str, str | None]:
    """Returns (assistant text, finish_reason)."""
    try:
        data = json.loads(raw)
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise NemotronError(f"unexpected response shape: {raw[:200]!r}") from e
    if isinstance(content, list):  # some servers return content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or "", choice.get("finish_reason")
