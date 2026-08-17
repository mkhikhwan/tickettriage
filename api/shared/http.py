"""Small helpers so every function returns a consistent JSON shape."""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from typing import Any, Dict, Optional

import azure.functions as func

JSON_HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
}


def json_response(payload: Any, status_code: int = 200,
                  extra_headers: Optional[Dict[str, str]] = None) -> func.HttpResponse:
    headers = dict(JSON_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    return func.HttpResponse(
        json.dumps(payload, default=str),
        status_code=status_code,
        headers=headers,
    )


def error_response(message: str, status_code: int = 400,
                   errors: Optional[Dict[str, str]] = None) -> func.HttpResponse:
    body: Dict[str, Any] = {"error": message}
    if errors:
        body["fields"] = errors
    return json_response(body, status_code)


def read_json(req: func.HttpRequest) -> Dict[str, Any]:
    """Parse a JSON body, raising ValueError with a friendly message."""
    try:
        body = req.get_json()
    except ValueError:
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    return body


def require_admin(req: func.HttpRequest, settings) -> Optional[func.HttpResponse]:
    """
    Guard admin-only endpoints.

    Two layers, in order of preference:

      1. Azure Static Web Apps built-in auth. When a user signs in, SWA injects
         an `x-ms-client-principal` header. Locking /api/tickets/* behind
         `allowedRoles` in staticwebapp.config.json is the production answer.
      2. A shared secret in the ADMIN_API_KEY app setting, sent as `x-admin-key`.
         Simple, demo-friendly, and enough to show you understand that admin
         actions must be authorised.

    If neither is configured the endpoint stays open, which is fine for a local
    demo and is flagged loudly by /api/health.
    """
    if settings.admin_api_key:
        supplied = req.headers.get("x-admin-key", "")
        if supplied != settings.admin_api_key:
            return error_response("Admin key missing or incorrect.", 401)
        return None

    if not settings.allow_anonymous_admin:
        principal = req.headers.get("x-ms-client-principal")
        if not principal:
            return error_response("Sign-in required for admin actions.", 401)

    return None


_rate_limit_lock = threading.Lock()
_request_history: Dict[str, list[float]] = defaultdict(list)


def get_client_ip(req: func.HttpRequest) -> str:
    """Detect the client's IP address from headers, falling back to localhost."""
    xff = req.headers.get("x-forwarded-for")
    if xff:
        # X-Forwarded-For can contain multiple IPs, the first one is the client
        return xff.split(",")[0].strip()
    client_ip = req.headers.get("client-ip")
    if client_ip:
        return client_ip.strip()
    return "127.0.0.1"


def check_rate_limit(req: func.HttpRequest, limit: int, period_seconds: int = 60) -> bool:
    """
    Check if a client IP is within rate limits.
    Returns True if allowed, False if rate limited.
    """
    ip = get_client_ip(req)
    now = time.time()
    with _rate_limit_lock:
        history = _request_history[ip]
        cutoff = now - period_seconds
        # Keep only timestamps in the current window
        history = [t for t in history if t > cutoff]
        if len(history) >= limit:
            _request_history[ip] = history
            return False
        history.append(now)
        _request_history[ip] = history
        return True

