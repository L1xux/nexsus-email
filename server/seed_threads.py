import asyncio
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import aiomysql

load_dotenv()

async def seed():
    conn = await aiomysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=3306,
        user=os.getenv("MARIADB_USER", "nexusmail"),
        password=os.getenv("MARIADB_PASSWORD", "nexusmail"),
        db=os.getenv("MARIADB_DATABASE", "nexusmail"),
    )
    async with conn.cursor() as cur:
        # Seed test threads for user 2
        now = datetime.now(timezone.utc)
        threads = [
            {
                "gmail_thread_id": f"test-thread-{i}",
                "subject": subject,
                "snippet": snippet,
                "status": status,
                "deadline": deadline,
                "message_count": 2,
                "last_message_at": now - timedelta(hours=hours_ago),
                "created_at": now - timedelta(hours=hours_ago + 1),
                "classification_confidence": confidence,
                "classification_reason": reason,
            }
            for i, (subject, snippet, status, deadline, hours_ago, confidence, reason) in enumerate([
                # INBOX
                ("Q3 Budget Review Required", "Hi, we need your input on the Q3 budget before Friday. Please review the attached spreadsheet.", "inbox", now + timedelta(days=2), 2, 0.91, "Action required: budget review by Friday deadline"),
                ("Project milestone update", "Team, please update your status on the current milestone. We need reports by EOD.", "inbox", None, 5, 0.85, "Task assigned, user needs to provide update"),
                ("Invoice #2024-0892 pending", "Your invoice is ready for review. Please confirm approval to proceed.", "inbox", now + timedelta(days=7), 8, 0.88, "Invoice needs user approval"),
                # TODO
                ("Contract renewal - Acme Corp", "Please review and sign the attached renewal contract by end of month.", "todo", now + timedelta(days=14), 1, 0.94, "Legal contract requires user action"),
                ("Feedback requested on proposal", "We'd appreciate your thoughts on the proposal we sent last week.", "todo", now + timedelta(days=3), 12, 0.79, "Response requested from user"),
                # WAITING
                ("RE: Job application - Senior Engineer", "Thank you for your application. We're reviewing candidates and will get back to you soon.", "waiting", None, 3, 0.87, "User awaiting recruiter response"),
                ("Quote sent for review", "I've sent over the quote as requested. Let me know if you have any questions.", "waiting", None, 24, 0.82, "User sent quote, awaiting customer reply"),
                # DONE
                ("Monthly newsletter - April", "Here are this month's updates from our team. Read at your convenience.", "done", None, 6, 0.95, "Informational newsletter, no action needed"),
                ("System maintenance notification", "Scheduled maintenance completed successfully. All systems operational.", "done", None, 48, 0.99, "Automated system notification"),
            ])
        ]

        for t in threads:
            await cur.execute(
                """INSERT INTO threads
                   (user_id, gmail_thread_id, subject, snippet, status, deadline,
                    message_count, last_message_at, created_at,
                    classification_confidence, classification_reason, is_read)
                   VALUES (2, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                   ON DUPLICATE KEY UPDATE subject=VALUES(subject), snippet=VALUES(snippet),
                   status=VALUES(status), deadline=VALUES(deadline),
                   classification_confidence=VALUES(classification_confidence),
                   classification_reason=VALUES(classification_reason)""",
                (t["gmail_thread_id"], t["subject"], t["snippet"], t["status"],
                 t["deadline"], t["message_count"], t["last_message_at"],
                 t["created_at"], t["classification_confidence"], t["classification_reason"])
            )
            print(f"Upserted thread: {t['subject'][:40]} [{t['status']}]")

        await conn.commit()

        # Seed some emails per thread
        email_templates = [
            ("Alice Chen", "alice@company.com", "Hi, sending this over for your review. Let me know if you have questions.", 0),
            ("Bob Kim", "bob@partner.io", "Thanks for getting back. I'll take a look and get back to you shortly.", 1),
            ("Carol Song", "carol@client.net", "Just checking in — any updates on this?", 0),
        ]
        for t in threads:
            for sender_name, sender_email, body, is_read in email_templates[:2]:
                received = t["last_message_at"] - timedelta(hours=len(email_templates) - is_read)
                await cur.execute(
                    """INSERT INTO emails
                       (user_id, gmail_message_id, thread_id, email_thread_id, subject,
                        sender, sender_email, snippet, body_text, status,
                        is_read, is_starred, received_at, classification_confidence,
                        classification_reason)
                       SELECT 2, %s, %s, id, %s, %s, %s, %s, %s, %s,
                              %s, 0, %s, %s, %s
                       FROM threads WHERE gmail_thread_id = %s""",
                    (f"{t['gmail_thread_id']}-msg-{sender_email}",
                     t["gmail_thread_id"],
                     t["subject"],
                     sender_name,
                     sender_email,
                     body[:100],
                     body,
                     t["status"],
                     is_read,
                     received,
                     t["classification_confidence"],
                     t["classification_reason"],
                     t["gmail_thread_id"])
                )
        print(f"Seeded emails for {len(threads)} threads")
        await conn.commit()

    conn.close()
    print("Done!")

asyncio.run(seed())
