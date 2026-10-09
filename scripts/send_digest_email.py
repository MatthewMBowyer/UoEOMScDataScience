#!/usr/bin/env python3
"""Email the digest produced by `personal_digest.py`.

Split out of the workflow so the sending logic is testable and readable, rather
than buried in YAML. Called by `.github/workflows/personal-digest.yml`.

Reads:
    digest.txt    - the body (written by the workflow)
    subject.txt   - the subject line

Environment:
    MAIL_USERNAME  sending address (Gmail)
    MAIL_PASSWORD  app password - never a normal account password
    MAIL_TO        recipient; defaults to MAIL_USERNAME

If the credentials are absent this exits 0 with a clear message instead of
failing the job: the digest is already in the run log, and a red build every
morning for a missing optional secret would just train the owner to ignore it.

Exit codes:
    0  sent, or deliberately skipped because email is not configured
    1  configured but sending failed (so the failure is visible)
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def main() -> int:
    user = os.environ.get("MAIL_USERNAME", "").strip()
    password = os.environ.get("MAIL_PASSWORD", "").strip()
    to = os.environ.get("MAIL_TO", "").strip() or user

    body = open("digest.txt", encoding="utf-8").read()
    subject = open("subject.txt", encoding="utf-8").read().strip() or "Your reminders"

    if not user or not password:
        print("Email is not configured (MAIL_USERNAME/MAIL_PASSWORD unset).")
        print("The digest is in the run log above. See docs/PERSONAL_PAGES.md.")
        return 0

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as s:
            s.login(user, password)
            s.send_message(msg)
    except Exception as exc:  # noqa: BLE001 - the message is the point
        print(f"Failed to send: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Sent to {to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
