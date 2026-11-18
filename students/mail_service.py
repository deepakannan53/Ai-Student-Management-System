import smtplib
import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
from django.conf import settings
from django.utils import timezone
from .models import StudentMail
from .ai_agents import classify_student_mail


def send_student_smtp_mail(student_profile, recipient_email: str, subject: str, body: str, category: str = 'staff') -> tuple[bool, str]:
    sender_email = student_profile.college_email
    sender_name = student_profile.user.get_full_name() or student_profile.user.username
    app_password = (student_profile.smtp_app_password or getattr(settings, 'DEFAULT_COLLEGE_SMTP_APP_PASSWORD', '')).strip()

    sent_live = False
    status_msg = "Sent & logged in Nothing SMS Outbox (Demo SMTP Mode)."

    if app_password:
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = f"{sender_name} <{sender_email}>"
            msg['To'] = recipient_email
            msg.set_content(body)

            with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10) as server:
                server.starttls()
                server.login(sender_email, app_password)
                server.send_message(msg)

            sent_live = True
            status_msg = f"Delivered live via SMTP to {recipient_email}."
        except Exception as exc:
            status_msg = f"SMTP relay failed ({exc}); archived in local Outbox."

    StudentMail.objects.create(
        student=student_profile,
        direction='OUTBOUND',
        sender_name=sender_name,
        sender_email=sender_email,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        category=category,
        ai_summary=f"Sent to {recipient_email}",
        is_read=True,
        sent_via_smtp=sent_live,
        timestamp=timezone.now(),
    )
    return sent_live, status_msg


def sync_and_triage_inbox(student_profile) -> int:
    app_password = (student_profile.smtp_app_password or getattr(settings, 'DEFAULT_COLLEGE_SMTP_APP_PASSWORD', '')).strip()
    if not app_password:
        return 0

    imported = 0
    try:
        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST)
        mail.login(student_profile.college_email, app_password)
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
        mail_ids = data[0].split()[-10:]

        for num in mail_ids:
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw_email = msg_data[0][1]
            parsed = email.message_from_bytes(raw_email)

            raw_subj, encoding = decode_header(parsed.get("Subject", "No Subject"))[0]
            subj = raw_subj.decode(encoding or "utf-8", errors="ignore") if isinstance(raw_subj, bytes) else raw_subj

            sender_full = parsed.get("From", "Unknown <unknown@college.edu>")
            sender_name = sender_full.split("<")[0].strip().strip('"') or sender_full
            sender_addr = sender_full.split("<")[-1].replace(">", "").strip() if "<" in sender_full else sender_full

            body = ""
            if parsed.is_multipart():
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                payload = parsed.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="ignore")

            ai_meta = classify_student_mail(sender_full, subj, body)
            StudentMail.objects.create(
                student=student_profile,
                direction='INBOUND',
                sender_name=sender_name[:120],
                sender_email=sender_addr[:254],
                recipient_email=student_profile.college_email,
                subject=subj[:255],
                body=body or "(Empty email body)",
                category=ai_meta["category"],
                ai_summary=ai_meta["ai_summary"][:255],
                extracted_deadline=ai_meta.get("extracted_deadline", "")[:100],
                is_urgent=ai_meta.get("is_urgent", False),
            )
            imported += 1
        mail.logout()
    except Exception:
        pass
    return imported
