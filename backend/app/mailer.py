"""Outgoing email. In console mode mail is written to the outbox table and the log only.
Emails never contain claim details — only codes or a prompt to open the app."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .db import Database, new_id, now_iso

log = logging.getLogger("haq.mail")


class Mailer:
    def __init__(self, settings, db: Database):
        self.settings = settings
        self.db = db

    def send(self, to_email: str, subject: str, body: str) -> str:
        """Returns the delivery status actually achieved: 'logged', 'sent' or 'failed'."""
        status, error = "logged", None
        if self.settings.email_mode == "smtp":
            try:
                msg = EmailMessage()
                msg["From"] = self.settings.smtp_from
                msg["To"] = to_email
                msg["Subject"] = subject
                msg.set_content(body)
                with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as s:
                    s.starttls()
                    if self.settings.smtp_user:
                        s.login(self.settings.smtp_user, self.settings.smtp_password)
                    s.send_message(msg)
                status = "sent"
            except Exception as exc:  # report, don't pretend
                status, error = "failed", type(exc).__name__
                log.warning("Email delivery failed (%s)", error)
        else:
            log.info("[console email] to=%s subject=%s\n%s", to_email, subject, body)
        with self.db.connection() as c:
            c.execute(
                "INSERT INTO email_outbox(id,to_email,subject,body,status,error,created_at) VALUES (?,?,?,?,?,?,?)",
                # Only development (console) mode keeps the body, so codes can be read in the dev outbox.
                (new_id(), to_email, subject, body if status == "logged" else "[not stored]", status, error, now_iso()),
            )
        return status
