"""Single-use email OTP authentication for Research OS."""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, smtplib, time
from email.message import EmailMessage
from pathlib import Path
from threading import Lock

OTP_TTL_SECONDS = 300
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
OTP_MAX_SENDS_PER_HOUR = 5
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
    try: os.chmod(temporary, 0o600)
    except OSError: pass
    os.replace(temporary, path)

def _send_email(email: str, code: str) -> None:
    host = (os.getenv("RESEARCH_OS_EMAIL_SMTP_HOST") or "").strip()
    sender = (os.getenv("RESEARCH_OS_EMAIL_FROM") or "").strip()
    if not host or not sender:
        raise EmailOTPError("Email OTP is not configured: SMTP host and sender are required", 503)
    port = int(os.getenv("RESEARCH_OS_EMAIL_SMTP_PORT", "587"))
    username = (os.getenv("RESEARCH_OS_EMAIL_SMTP_USER") or "").strip()
    password = os.getenv("RESEARCH_OS_EMAIL_SMTP_PASSWORD") or ""
    message = EmailMessage()
    message["Subject"] = "Your Research OS sign-in code"
    message["From"], message["To"] = sender, email
    message.set_content(f"Your Research OS verification code is {code}. It expires in five minutes and can only be used once. Ignore this email if you did not request it.")
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as client:
                if username: client.login(username, password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as client:
                client.ehlo(); client.starttls(); client.ehlo()
                if username: client.login(username, password)
                client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailOTPError("Email delivery failed; check the server SMTP configuration", 503) from exc

def start_email_otp(email_value: str, *, now: int | None = None) -> dict:
    email = _normalize_email(email_value)
    current = int(time.time()) if now is None else int(now)
    key = hashlib.sha256(email.encode()).hexdigest()
    code, salt = f"{secrets.randbelow(1_000_000):06d}", secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()
    with _LOCK:
        state = _read()
        previous = state.get(key) if isinstance(state.get(key), dict) else {}
        sent = [int(t) for t in previous.get("sent_at", []) if current - int(t) < 3600]
        if sent and current - sent[-1] < OTP_RESEND_SECONDS:
            raise EmailOTPError("Please wait before requesting another code", 429)
        if len(sent) >= OTP_MAX_SENDS_PER_HOUR:
            raise EmailOTPError("Too many verification codes requested; try again later", 429)
        state[key] = {"email": email, "salt": salt, "digest": digest, "created_at": current, "expires_at": current + OTP_TTL_SECONDS, "attempts": 0, "sent_at": sent + [current]}
        _write(state)
    try:
        _send_email(email, code)
    except Exception:
        with _LOCK:
            state = _read(); state.pop(key, None); _write(state)
        raise
    return {"accepted": True, "expires_in": OTP_TTL_SECONDS, "delivery": "email"}

def verify_email_otp(email_value: str, code_value: str, *, now: int | None = None) -> str:
    email, code = _normalize_email(email_value), str(code_value or "").strip()
    if len(code) != 6 or not code.isdigit():
        raise EmailOTPError("The verification code is invalid", 401)
    current = int(time.time()) if now is None else int(now)
    key = hashlib.sha256(email.encode()).hexdigest()
    with _LOCK:
        state = _read(); challenge = state.get(key)
        if not isinstance(challenge, dict):
            raise EmailOTPError("The verification code is missing or expired", 401)
        if int(challenge.get("expires_at", 0)) <= current:
            state.pop(key, None); _write(state)
            raise EmailOTPError("The verification code has expired", 401)
        attempts = int(challenge.get("attempts", 0)) + 1
        challenge["attempts"] = attempts
        supplied = hashlib.sha256(f"{challenge.get('salt', '')}:{code}".encode()).hexdigest()
        if attempts > OTP_MAX_ATTEMPTS or not hmac.compare_digest(str(challenge.get("digest") or ""), supplied):
            if attempts >= OTP_MAX_ATTEMPTS: state.pop(key, None)
            else: state[key] = challenge
            _write(state)
            raise EmailOTPError("The verification code is invalid", 401)
        state.pop(key, None); _write(state)
    return email
