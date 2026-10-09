#!/usr/bin/env python3
"""Send the personal digest through Gmail SMTP.

The email is sent as multipart/alternative: a plain-text part and a styled HTML
part. Only the workflow's `digest.txt` is required; the HTML is rendered here by
`personal_digest.render_html`, so the email looks good without any change to the
workflow (which the publishing token cannot push anyway).

If the HTML render fails for any reason the mail still goes out as plain text.
A reminder that arrives ugly beats one that does not arrive.
"""

import datetime as dt
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

_HERE = os.path.dirname(os.path.abspath(__file__))
_CWD = os.getcwd()
sys.path.insert(0, _HERE)
# importing personal_digest chdir()s to the repo root as a side effect, so the
# directory the caller ran us from is restored: digest.txt and subject.txt are
# read relative to where the workflow invoked this script.
import personal_digest as PD  # noqa: E402

os.chdir(_CWD)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def build_html() -> str | None:
    """The styled version of the same digest, or None if it cannot be built."""
    # PD.load() reads personal/data/*.json relative to the cwd, so the build runs
    # from the repo root and the caller's cwd is put back afterwards.
    prev = os.getcwd()
    try:
        os.chdir(os.path.dirname(_HERE))
        sports = PD.load("sports.json")
        hubby = PD.load("good_hubby.json")
        return PD.render_html(sports, hubby, dt.date.today(), 10)
    except Exception as exc:  # noqa: BLE001 - never block the email on cosmetics
        print(
            f"NOTE: HTML body unavailable ({type(exc).__name__}: {exc}); "
            "sending plain text only.",
            flush=True,
        )
        return None
    finally:
        os.chdir(prev)


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
    # Text first, then HTML. In multipart/alternative the LAST part is the one a
    # capable client displays, so the styled body must be added second.
    msg.set_content(body)
    html = build_html()
    if html:
        msg.add_alternative(html, subtype="html")

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

        kind = "HTML + plain text" if html else "plain text"
        print(f"SUCCESS: Email sent to {recipient} ({kind})!", flush=True)
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
