"""Single-use email OTP authentication for Research OS."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock

OTP_TTL_SECONDS = 300
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
OTP_MAX_SENDS_PER_HOUR = 5
RESEND_EMAILS_URL = "https://api.resend.com/emails"
_LOCK = Lock()


class EmailOTPError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _root() -> Path:
    configured = (os.getenv("RESEARCH_OS_DATA_DIR") or "").strip()
    root = Path(configured).expanduser() if configured else (
        Path(os.getenv("PROGRAMDATA") or r"C:\ProgramData") / "ResearchOS"
        if os.name == "nt" else Path.home() / ".local" / "share" / "research-os"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path() -> Path:
    return _root() / "email_otp_challenges.json"


def _code_digest(salt: str, code: str) -> str:
    secret = (
        os.getenv("RESEARCH_OS_EMAIL_OTP_SECRET")
        or os.getenv("RESEARCH_OS_SESSION_SECRET")
        or ""
    ).encode("utf-8")
    if not secret:
        raise EmailOTPError(
            "Email OTP requires RESEARCH_OS_EMAIL_OTP_SECRET or RESEARCH_OS_SESSION_SECRET",
            503,
        )
    return hmac.new(secret, f"{salt}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or email.count("@") != 1:
        raise EmailOTPError("A valid email address is required")
    local, domain = email.rsplit("@", 1)
    if not local or "." not in domain or any(c.isspace() for c in email):
        raise EmailOTPError("A valid email address is required")
    return email


def _read() -> dict:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write(state: dict) -> None:
    path = _path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def _send_email(email: str, code: str) -> None:
    """Send an OTP through Resend's HTTPS API; never fall back to SMTP."""
    api_key = (os.getenv("RESEARCH_OS_EMAIL_API_KEY") or "").strip()
    sender = (os.getenv("RESEARCH_OS_EMAIL_FROM") or "").strip()
    provider = (os.getenv("RESEARCH_OS_EMAIL_PROVIDER") or "resend").strip().lower()

    if provider != "resend":
        raise EmailOTPError("Unsupported Email API provider; configure resend", 503)
    if not api_key or not sender:
        raise EmailOTPError(
            "Email OTP is not configured: RESEARCH_OS_EMAIL_API_KEY and RESEARCH_OS_EMAIL_FROM are required",
            503,
        )

    payload = {
        "from": sender,
        "to": [email],
        "subject": "Your Research OS sign-in code",
        "text": (
            f"Your Research OS verification code is {code}. "
            "It expires in five minutes and can only be used once. "
            "Ignore this email if you did not request it."
        ),
    }
    request = urllib.request.Request(
        RESEND_EMAILS_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ResearchOS/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = int(getattr(response, "status", 200))
            if status < 200 or status >= 300:
                raise EmailOTPError("Email API rejected the delivery request", 503)
    except EmailOTPError:
        raise
    except urllib.error.HTTPError as exc:
        # Do not return provider response bodies: they may contain account data.
        raise EmailOTPError(
            "Email API rejected the delivery request; check the API key and verified sender",
            503,
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise EmailOTPError(
            "Email API is unreachable; check outbound HTTPS connectivity and provider status",
            503,
        ) from exc


def start_email_otp(email_value: str, *, now: int | None = None) -> dict:
    email = _normalize_email(email_value)
    current = int(time.time()) if now is None else int(now)
    key = hashlib.sha256(email.encode()).hexdigest()
    code, salt = f"{secrets.randbelow(1_000_000):06d}", secrets.token_hex(16)
    digest = _code_digest(salt, code)
    with _LOCK:
        state = _read()
        previous = state.get(key) if isinstance(state.get(key), dict) else {}
        sent = [int(t) for t in previous.get("sent_at", []) if current - int(t) < 3600]
        if sent and current - sent[-1] < OTP_RESEND_SECONDS:
            raise EmailOTPError("Please wait before requesting another code", 429)
        if len(sent) >= OTP_MAX_SENDS_PER_HOUR:
            raise EmailOTPError("Too many verification codes requested; try again later", 429)
        state[key] = {
            "email": email,
            "salt": salt,
            "digest": digest,
            "created_at": current,
            "expires_at": current + OTP_TTL_SECONDS,
            "attempts": 0,
            "sent_at": sent + [current],
        }
        _write(state)
    try:
        _send_email(email, code)
    except Exception:
        with _LOCK:
            state = _read()
            state.pop(key, None)
            _write(state)
        raise
    return {"accepted": True, "expires_in": OTP_TTL_SECONDS, "delivery": "email"}


def verify_email_otp(email_value: str, code_value: str, *, now: int | None = None) -> str:
    email, code = _normalize_email(email_value), str(code_value or "").strip()
    if len(code) != 6 or not code.isdigit():
        raise EmailOTPError("The verification code is invalid", 401)
    current = int(time.time()) if now is None else int(now)
    key = hashlib.sha256(email.encode()).hexdigest()
    with _LOCK:
        state = _read()
        challenge = state.get(key)
        if not isinstance(challenge, dict):
            raise EmailOTPError("The verification code is missing or expired", 401)
        if int(challenge.get("expires_at", 0)) <= current:
            challenge["digest"] = ""
            challenge["salt"] = ""
            challenge["expires_at"] = 0
            state[key] = challenge
            _write(state)
            raise EmailOTPError("The verification code has expired", 401)
        attempts = int(challenge.get("attempts", 0)) + 1
        challenge["attempts"] = attempts
        supplied = _code_digest(str(challenge.get("salt") or ""), code)
        if attempts > OTP_MAX_ATTEMPTS or not hmac.compare_digest(
            str(challenge.get("digest") or ""), supplied
        ):
            if attempts >= OTP_MAX_ATTEMPTS:
                challenge["digest"] = ""
                challenge["salt"] = ""
                challenge["expires_at"] = 0
            state[key] = challenge
            _write(state)
            raise EmailOTPError("The verification code is invalid", 401)
        challenge["digest"] = ""
        challenge["salt"] = ""
        challenge["expires_at"] = 0
        state[key] = challenge
        _write(state)
    return email
