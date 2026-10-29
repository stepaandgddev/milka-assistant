"""Test Milky's configured SMTP connection without sending mail.

Run from the project root with:
    PYTHONPATH=app python scripts/test_email_smtp.py
"""

from __future__ import annotations

import smtplib

from settings_store import load_settings


def main():
    settings = load_settings()
    config = (
        settings.get("addons", {}).get("settings", {}).get("email", {})
    )
    host = str(config.get("smtp_host") or "").strip()
    port = int(config.get("smtp_port") or 25)
    security = str(config.get("smtp_security") or "none").lower()
    username = str(
        config.get("username") or config.get("email_address") or ""
    ).strip()
    password = str(config.get("password") or "")

    print(f"SMTP server: {host}:{port} ({security})")
    print(f"Username configured: {'yes' if username else 'no'}")
    print(f"Password configured: {'yes' if password else 'no'}")

    with smtplib.SMTP(host, port, timeout=15) as client:
        client.ehlo()
        print("Connection: OK")
        auth = "auth" in client.esmtp_features
        print(f"AUTH advertised: {'yes' if auth else 'no'}")
        if auth and username and password:
            client.login(username, password)
            print("Authentication: OK")
        elif not auth:
            print("Authentication: skipped; server does not advertise AUTH")
        else:
            print("Authentication: skipped; credentials are incomplete")
    print("No email was sent.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"SMTP test failed: {type(error).__name__}: {error}")
        raise SystemExit(1)
