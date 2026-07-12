import pandas as pd
import smtplib
import time
import re
import sys
import json
from email.message import EmailMessage

def log(msg):
    print(msg, flush=True)

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def connect_smtp(smtp_server, smtp_port, email_address, email_password):
    log("[SMTP] Connecting...")
    server = smtplib.SMTP(smtp_server, smtp_port, timeout=60)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(email_address, email_password)
    log("[SMTP] Connected.")
    return server

def run(csv_file, email_address, email_password, smtp_server, smtp_port, subject, message, delay):
    try:
        df = pd.read_csv(csv_file, encoding="utf-8-sig", engine="python", sep=",")
        log(f"[INFO] CSV loaded: {len(df)} rows")
    except Exception as e:
        log(f"[ERROR] Failed to load CSV: {e}")
        return

    email_col = next((col for col in df.columns if "email" in col.lower()), None)
    if not email_col:
        log("[ERROR] No Email column found in CSV.")
        return

    emails = []
    for value in df[email_col].dropna():
        value = str(value).strip()
        for part in re.split(r"[;,]", value):
            part = part.strip()
            if EMAIL_REGEX.match(part):
                emails.append(part)

    email_list = sorted(list(set(emails)))
    log(f"[INFO] Found {len(email_list)} valid emails.")

    if not email_list:
        log("[ERROR] No valid emails found.")
        return

    try:
        server = connect_smtp(smtp_server, int(smtp_port), email_address, email_password)
    except Exception as e:
        log(f"[ERROR] SMTP Login Failed: {e}")
        return

    success = []
    failed = []
    total = len(email_list)

    for index, recipient in enumerate(email_list, start=1):
        try:
            log(f"[{index}/{total}] Sending to: {recipient}")
            msg = EmailMessage()
            msg["From"] = email_address
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.set_content(message)
            server.send_message(msg)
            log(f"[OK] Sent to {recipient}")
            success.append(recipient)
            time.sleep(int(delay))
        except Exception as e:
            log(f"[FAIL] {recipient} — {e}")
            failed.append(recipient)
            try:
                server.quit()
            except:
                pass
            try:
                server = connect_smtp(smtp_server, int(smtp_port), email_address, email_password)
            except Exception as re_err:
                log(f"[ERROR] Reconnect failed: {re_err}")
                break

    try:
        server.quit()
    except:
        pass

    log(f"[DONE] Sent: {len(success)}, Failed: {len(failed)}, Total: {total}")

if __name__ == "__main__":
    args = json.loads(sys.argv[1])
    run(
        args["csv_file"],
        args["email_address"],
        args["email_password"],
        args["smtp_server"],
        args["smtp_port"],
        args["subject"],
        args["message"],
        args["delay"]
    )
