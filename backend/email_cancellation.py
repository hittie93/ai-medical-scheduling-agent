"""
Email cancellation processor.

Checks IMAP inbox for unread emails containing 'cancel' and reopens the matching
appointment slot in data/appointments.xlsx based on patient_email.
"""

import os
import imaplib
import email
from email.header import decode_header
from typing import Optional
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

try:
    from backend.remainders import ReminderSystem
except ModuleNotFoundError:
    from remainders import ReminderSystem


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None else default


def _msg_text(msg) -> str:
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get('Content-Disposition') or '')
            if ctype == 'text/plain' and 'attachment' not in disp:
                try:
                    parts.append(part.get_payload(decode=True).decode(errors='ignore'))
                except Exception:
                    pass
    else:
        try:
            parts.append(msg.get_payload(decode=True).decode(errors='ignore'))
        except Exception:
            pass
    return '\n'.join(parts)


def check_email_cancellations() -> int:
    """
    Check IMAP inbox for unread 'cancel' emails and reopen matching slots.
    Returns number of processed cancellations.
    """
    user = _get_env('EMAIL_USER')
    pwd = _get_env('EMAIL_PASSWORD')
    if not user or not pwd:
        return 0

    processed = 0
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(user, pwd)
    mail.select('inbox')

    status, data = mail.search(None, '(UNSEEN)')
    if status != 'OK':
        mail.logout()
        return 0

    rs = ReminderSystem()

    for num in data[0].split():
        try:
            status, msg_data = mail.fetch(num, '(RFC822)')
            if status != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subj, enc = decode_header(msg.get('Subject') or '')[0]
            if isinstance(subj, bytes):
                subj = subj.decode(errors='ignore')
            from_addr = email.utils.parseaddr(msg.get('From') or '')[1]
            body = _msg_text(msg)
            text = f"{subj}\n{body}".lower()

            if 'cancel' not in text:
                continue

            # Find appointment by patient_email
            xlsx_path = Path('data/appointments.xlsx')
            if not xlsx_path.exists():
                continue
            try:
                df = pd.read_excel(xlsx_path)
            except Exception:
                continue

            email_col = 'patient_email' if 'patient_email' in df.columns else None
            if not email_col:
                for c in df.columns:
                    if 'email' in c.lower():
                        email_col = c
                        break
            if not email_col:
                continue

            subset = df[df[email_col].astype(str).str.lower() == (from_addr or '').lower()]
            if subset.empty:
                continue

            # latest by created_at if present
            if 'created_at' in subset.columns:
                subset = subset.sort_values('created_at')
            last = subset.iloc[-1]
            doctor = str(last.get('doctor', ''))
            date = str(last.get('date', ''))
            time = str(last.get('time', ''))
            appt_id = str(last.get('appointment_id', ''))

            if rs.reopen_slot(appointment_id=appt_id, doctor=doctor, date=date, time=time, channel="email"):
                processed += 1

            # Mark as seen
            mail.store(num, '+FLAGS', '\\Seen')

        except Exception:
            # best-effort; continue
            continue

    mail.logout()
    return processed


if __name__ == '__main__':
    cnt = check_email_cancellations()
    print(f"Processed {cnt} cancellation(s)")


