import imaplib
import email
from email.header import decode_header
from openai import OpenAI
from dotenv import load_dotenv
from os import getenv
from datetime import datetime,timedelta


load_dotenv()


# --- CONFIGURATION ---
EMAIL_USER = getenv("EMAIL")
EMAIL_PASS = getenv("PASSWORD")  # The one you just generated
OPENROUTER_KEY = getenv("OPEN_ROUTER_API")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

def fetch_and_summarize():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    # 1. Generate today's date in IMAP format: DD-Mon-YYYY
    today = datetime.now().strftime("%d-%b-%Y")
    # today = "17-Mar-2026"
    # print(today)

    # 2. Search for UNSEEN (Unread) AND emails from TODAY
    # This combines the two criteria
    search_query = f'(UNSEEN ON {today})'
    status, messages = mail.search(None, search_query)
    
    email_ids = messages[0].split()

    if not email_ids:
        print(f"No new emails found for today ({today}).")
        return

    print(f"Summarizing {len(email_ids)} unread emails from today...\n")

    for e_id in email_ids:
        # Use BODY.PEEK so we don't mark them as read until we're done
        _, msg_data = mail.fetch(e_id, '(BODY.PEEK[])')
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Decode Subject
                subject_raw = msg.get("Subject", "No Subject")
                subject, encoding = decode_header(subject_raw)[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                # Extract Body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            content = part.get_payload(decode=True)
                            if content:
                                body = content.decode(errors='ignore')
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors='ignore')

                # 3. Summarize with OpenRouter
                prompt = f"Provide a short summary of this email:\nSubject: {subject}\nContent: {body[:1500]}"
                print(subject)
                print(body)
                print("="*40)
                # try:
                #     response = client.chat.completions.create(
                #         model="openrouter/hunter-alpha",
                #         messages=[{"role": "user", "content": prompt}]
                #     )
                #     summary = response.choices[0].message.content
                #     print(f"📌 SUBJECT: {subject}")
                #     print(f"📝 SUMMARY: {summary}\n")
                # except Exception as e:
                #     print(f"Error summarizing email '{subject}': {e}")

    mail.logout()

if __name__ == "__main__":
    fetch_and_summarize()