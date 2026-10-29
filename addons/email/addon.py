"""Send and receive email through SMTP and IMAP.

The account is configured in Settings -> Skills. Passwords are kept in the
normal Milky settings file, so an app password is recommended.
"""

from __future__ import annotations

import email
import email.header
import imaplib
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from addon_api import tool


DEFAULTS = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "smtp_security": "ssl",
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "imap_security": "ssl",
    "mailbox": "INBOX",
    "max_message_chars": 12000,
}


def _settings(ctx):
    settings = getattr(ctx, "settings", None)
    return settings if isinstance(settings, dict) else {}


def _value(ctx, key):
    return _settings(ctx).get(key, DEFAULTS.get(key, ""))


def _credentials(ctx):
    username = str(_value(ctx, "username") or _value(ctx, "email_address") or "").strip()
    password = str(_value(ctx, "password") or "")
    if not username or not password:
        raise RuntimeError(
            "Email is not configured. Set the username and password in Settings -> Skills."
        )
    return username, password


def _port(ctx, key):
    try:
        return max(1, min(65535, int(_value(ctx, key))))
    except (TypeError, ValueError):
        return int(DEFAULTS[key])


def _smtp_client(ctx):
    host = str(_value(ctx, "smtp_host") or "").strip()
    security = str(_value(ctx, "smtp_security") or "ssl").lower()
    port = _port(ctx, "smtp_port")
    if not host:
        raise RuntimeError("SMTP host is not configured.")
    try:
        if security == "ssl":
            client = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            client = smtplib.SMTP(host, port, timeout=30)
            client.ehlo()
            if security == "starttls":
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
        return client
    except (OSError, smtplib.SMTPException) as error:
        raise RuntimeError(
            f"Could not connect to SMTP {host}:{port} using {security.upper()}: {error}"
        ) from error


def _smtp_error(error):
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return (
            "SMTP authentication failed. Check the username and password/app "
            "password, and make sure SMTP access is enabled for this account."
        )
    if isinstance(error, smtplib.SMTPServerDisconnected):
        return "The SMTP server closed the connection. Check the port and TLS mode."
    if isinstance(error, smtplib.SMTPResponseException):
        detail = error.smtp_error.decode(errors="replace") if isinstance(error.smtp_error, bytes) else str(error.smtp_error)
        return f"SMTP server rejected the request ({error.smtp_code}): {detail}"
    if isinstance(error, OSError):
        return f"Network error while connecting to SMTP: {error}"
    return str(error) or error.__class__.__name__


def _login_if_supported(client, username, password):
    """Authenticate when the server offers AUTH; support local open relays."""
    # SMTP_SSL does not necessarily populate esmtp_features until EHLO is
    # sent. Without this call the addon could incorrectly believe AUTH was
    # unavailable and send the message without logging in.
    client.ehlo()
    if "auth" not in getattr(client, "esmtp_features", {}):
        return False
    client.login(username, password)
    return True


def _decode_header(value):
    parts = email.header.decode_header(value or "")
    result = []
    for text, charset in parts:
        if isinstance(text, bytes):
            result.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(text))
    return "".join(result)


def _message_text(message):
    chunks = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() not in ("text/plain", "text/html"):
                continue
            payload = part.get_payload(decode=True)
            if payload:
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
            if chunks and part.get_content_type() == "text/plain":
                break
    else:
        payload = message.get_payload(decode=True)
        if payload:
            chunks.append(payload.decode(message.get_content_charset() or "utf-8", errors="replace"))
    text = "\n".join(chunks).strip()
    limit = max(1000, min(50000, int(_value_from_message_settings(message))))
    return text[:limit]


def _value_from_message_settings(message):
    # The limit is applied by callers; this fallback keeps malformed messages safe.
    return DEFAULTS["max_message_chars"]


def _message_summary(message, uid):
    return {
        "id": str(uid),
        "subject": _decode_header(message.get("Subject", "")),
        "from": _decode_header(message.get("From", "")),
        "to": _decode_header(message.get("To", "")),
        "date": message.get("Date", ""),
        "body": _message_text(message),
    }


def _imap_ssl_context(ctx):
    verify = _settings(ctx).get("imap_verify_certificate", False)
    if isinstance(verify, str):
        verify = verify.strip().lower() in ("1", "true", "yes", "on")
    if verify:
        return ssl.create_default_context()
    # The local Docker Mailserver uses a self-signed certificate. This is
    # intentionally opt-in through the visual setting and should not be used
    # for an untrusted or internet-facing IMAP server.
    return ssl._create_unverified_context()


@tool(
    "send_email",
    "Send an email using the configured SMTP account.",
    {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient address."},
            "subject": {"type": "string", "description": "Email subject."},
            "body": {"type": "string", "description": "Plain-text email body."},
        },
        "required": ["to", "subject", "body"],
    },
)
def send_email(ctx, to, subject, body):
    username, password = _credentials(ctx)
    recipient = parseaddr(str(to))[1]
    if not recipient or "@" not in recipient:
        raise RuntimeError("The recipient address is invalid.")
    message = EmailMessage()
    message["From"] = str(_value(ctx, "email_address") or username).strip()
    message["To"] = recipient
    message["Subject"] = str(subject or "").strip()[:300]
    # Some mail filters, including amavisd-new, reject messages without the
    # mandatory Date header. Message-ID also makes downstream threading and
    # bounce diagnostics reliable when using a raw SMTP relay.
    message["Date"] = formatdate(localtime=False, usegmt=True)
    message["Message-ID"] = make_msgid()
    message.set_content(str(body or "")[:100000])

    try:
        with _smtp_client(ctx) as client:
            _login_if_supported(client, username, password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise RuntimeError(_smtp_error(error)) from error
    return f"Email sent to {recipient}."


@tool(
    "test_smtp",
    "Test the configured SMTP connection and authentication without sending an email.",
)
def test_smtp(ctx):
    username, password = _credentials(ctx)
    try:
        with _smtp_client(ctx) as client:
            authenticated = _login_if_supported(client, username, password)
    except (OSError, smtplib.SMTPException) as error:
        raise RuntimeError(_smtp_error(error)) from error
    if authenticated:
        return "SMTP connection and authentication succeeded. No email was sent."
    return "SMTP connection succeeded. This server does not advertise AUTH; no login was attempted. No email was sent."


@tool(
    "get_emails",
    "Get recent emails from the configured IMAP mailbox, including sender, subject and body.",
    {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "Number of recent messages to return.",
            },
            "unread_only": {
                "type": "boolean",
                "description": "Only return unread messages.",
            },
        },
    },
)
def get_emails(ctx, limit=5, unread_only=False):
    username, password = _credentials(ctx)
    try:
        count = max(1, min(20, int(limit)))
    except (TypeError, ValueError):
        count = 5
    host = str(_value(ctx, "imap_host") or "").strip()
    security = str(_value(ctx, "imap_security") or "ssl").lower()
    mailbox = str(_value(ctx, "mailbox") or "INBOX").strip() or "INBOX"
    if not host:
        raise RuntimeError("IMAP host is not configured.")
    client = None
    try:
        if security == "ssl":
            client = imaplib.IMAP4_SSL(
                host,
                _port(ctx, "imap_port"),
                ssl_context=_imap_ssl_context(ctx),
            )
        else:
            client = imaplib.IMAP4(host, _port(ctx, "imap_port"))
        client.login(username, password)
        status, _ = client.select(mailbox, readonly=True)
        if status != "OK":
            raise RuntimeError(f"Could not open mailbox {mailbox!r}.")
        criteria = "UNSEEN" if unread_only else "ALL"
        status, data = client.uid("search", None, criteria)
        if status != "OK":
            raise RuntimeError("Could not search the mailbox.")
        ids = (data[0] or b"").split()[-count:]
        results = []
        max_chars = max(1000, min(50000, int(_value(ctx, "max_message_chars"))))
        for uid in reversed(ids):
            status, fetched = client.uid("fetch", uid, "(RFC822)")
            if status != "OK":
                continue
            raw = next((item[1] for item in fetched if isinstance(item, tuple)), None)
            if not raw:
                continue
            message = email.message_from_bytes(raw)
            item = _message_summary(message, uid.decode(errors="replace"))
            item["body"] = item["body"][:max_chars]
            results.append(item)
        return {"mailbox": mailbox, "count": len(results), "emails": results}
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass
