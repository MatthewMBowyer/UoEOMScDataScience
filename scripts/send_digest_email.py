
#!/usr/bin/env python3
"""Send the personal digest through Gmail SMTP."""

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def main():
    username = os.environ.get("MAIL_USERNAME", "").strip()
    password = os.environ.get("MAIL_PASSWORD", "").strip()
    recipient = os.environ.get("MAIL_TO", "").strip() or username

    if not username or not password:
        print("ERROR: MAIL_USERNAME or MAIL_PASSWORD missing")
        return 1

    with open("digest.txt", encoding="utf-8") as f:
        body = f.read()

    with open("subject.txt", encoding="utf-8") as f:
        subject = f.read().strip() or "Your reminders"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = recipient
    msg.set_content(body)

    stage = "Connecting"

    try:
        print("1. Connecting to Gmail...", flush=True)

        with smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_PORT,
            timeout=20,
            context=ssl.create_default_context()
        ) as smtp:

            stage = "EHLO"
            print("2. Testing SMTP greeting...", flush=True)
            code, response = smtp.ehlo()
            print(f"EHLO response code: {code}", flush=True)

            if code != 250:
                raise RuntimeError(
                    f"Gmail rejected EHLO: {code}"
                )

            stage = "Authentication"
            print("3. Authenticating...", flush=True)
            smtp.login(username, password)

            stage = "Sending"
            print("4. Sending email...", flush=True)
            smtp.send_message(msg)

        print("SUCCESS: Email sent!", flush=True)
        return 0

    except Exception as exc:
        print(
            f"FAILED during {stage}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
