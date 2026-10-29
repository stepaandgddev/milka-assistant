# Email for Milky

This addon sends and receives messages through SMTP and IMAP. Configure it in
**Settings → Skills → Email**.

## Settings

- Email address, username and password/app password
- SMTP host, port and security mode
- IMAP host, port and security mode
- Optional IMAP certificate verification. It is disabled by default for the
  local self-signed Docker Mailserver certificate.
- Mailbox name and maximum message body size

The password is stored in Milky's normal settings file. Prefer a provider app
password instead of your main account password. Do not enable this addon for
an account whose credentials you do not trust Milky to use.

## Tools

- `send_email` — send a plain-text message to one recipient.
- `get_emails` — fetch recent messages, optionally unread only.
- `test_smtp` — check the SMTP connection and login without sending a message.

The addon uses Python's standard library and needs no extra packages.

For a local Docker Mailserver using IMAPS, use port `993` and `SSL/TLS`. The
certificate verification checkbox may remain disabled only when the server is
trusted and reachable exclusively through your private network. Do not disable
certificate verification for an untrusted or internet-facing server.

If the web interface works but SMTP does not, run `test_smtp` first. The web
interface and SMTP are separate services: verify the SMTP hostname, port and
security mode. Port `465` uses **SSL/TLS**, while port `587` normally uses
**STARTTLS**. Many providers require an app password for SMTP even when the
normal account password works on the web.
