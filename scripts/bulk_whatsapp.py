# import pandas as pd
# import time
# import urllib.parse
# import re
# import sys
# import json
# import requests

# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC

# SERVER_BASE = "http://localhost:5000"

# def log(msg):
#     print(msg, flush=True)

# def wait_for_ready_signal():
#     """
#     Poll the server's /api/whatsapp/wait endpoint instead of calling
#     input(), which would block the server thread.
#     """
#     log("[WAIT] Waiting for QR scan confirmation from dashboard...")
#     try:
#         # Long-poll: server holds the connection until user clicks button
#         resp = requests.get(f"{SERVER_BASE}/api/whatsapp/wait", timeout=310)
#         if resp.json().get("status") == "ready":
#             log("[INFO] QR confirmed. Starting to send messages...")
#             return True
#         else:
#             log("[ERROR] QR wait timed out.")
#             return False
#     except Exception as e:
#         log(f"[ERROR] Could not connect to server for QR wait: {e}")
#         return False

# def run(csv_file, phone_column, message, delay, profile_path):
#     try:
#         df = pd.read_csv(csv_file)
#         log(f"[INFO] CSV loaded: {len(df)} rows")
#     except Exception as e:
#         log(f"[ERROR] Failed to load CSV: {e}")
#         return

#     if phone_column not in df.columns:
#         log(f"[ERROR] Column '{phone_column}' not found. Available: {list(df.columns)}")
#         return

#     numbers = df[phone_column].dropna().astype(str).tolist()
#     log(f"[INFO] Found {len(numbers)} phone numbers")

#     options = Options()
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     if profile_path:
#         options.add_argument(f"--user-data-dir={profile_path}")

#     driver = webdriver.Chrome(options=options)
#     driver.get("https://web.whatsapp.com")

#     log("[WAIT] WhatsApp Web is open. Please scan the QR code.")
#     log("[ACTION] Click 'QR Scanned – Continue' in the dashboard when ready.")

#     # Non-blocking wait via server signal
#     if not wait_for_ready_signal():
#         driver.quit()
#         return

#     log("[INFO] Starting to send messages...")

#     success = []
#     failed = []

#     for number in numbers:
#         try:
#             cleaned = re.sub(r"\D", "", number)
#             if not cleaned:
#                 continue

#             encoded_message = urllib.parse.quote(message)
#             url = f"https://web.whatsapp.com/send?phone={cleaned}&text={encoded_message}"

#             log(f"[SENDING] {cleaned}")
#             driver.get(url)

#             box = WebDriverWait(driver, 20).until(
#                 EC.presence_of_element_located(
#                     (By.XPATH, '//div[@contenteditable="true"][@data-tab]')
#                 )
#             )
#             time.sleep(2)
#             box.send_keys(Keys.ENTER)
#             log(f"[OK] Sent to {cleaned}")
#             success.append(cleaned)
#             time.sleep(int(delay))
#         except Exception as e:
#             log(f"[FAIL] {number} — {e}")
#             failed.append(number)

#     log(f"[DONE] Sent: {len(success)}, Failed: {len(failed)}, Total: {len(numbers)}")
#     driver.quit()


# if __name__ == "__main__":
#     args = json.loads(sys.argv[1])
#     run(
#         args["csv_file"],
#         args["phone_column"],
#         args["message"],
#         args["delay"],
#         args.get("profile_path", "")
#     )





import pandas as pd
import time
import urllib.parse
import re
import sys
import json
import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

SERVER_BASE = "http://localhost:5000"

def log(msg):
    print(msg, flush=True)

def wait_for_ready_signal():
    log("[WAIT] Waiting for QR scan confirmation from dashboard...")
    try:
        resp = requests.get(f"{SERVER_BASE}/api/whatsapp/wait", timeout=310)
        if resp.json().get("status") == "ready":
            log("[INFO] QR confirmed. Starting to send messages...")
            return True
        else:
            log("[ERROR] QR wait timed out.")
            return False
    except Exception as e:
        log(f"[ERROR] Could not connect to server for QR wait: {e}")
        return False

# ── Multiple selectors ranked by reliability ──────────────────────────────────
# WhatsApp Web changes its DOM often; we try each one in order.
SEND_BOX_SELECTORS = [
    # Most reliable: the footer input area (current as of 2024–2025)
    (By.XPATH, '//div[@role="textbox" and @contenteditable="true"]'),
    # Fallback 1: data-tab attribute (older versions)
    (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]'),
    (By.XPATH, '//div[@contenteditable="true"][@data-tab="6"]'),
    # Fallback 2: footer-scoped search
    (By.XPATH, '//footer//div[@contenteditable="true"]'),
    # Fallback 3: aria-label (localized, but often present)
    (By.XPATH, '//div[@aria-label="Type a message"]'),
    (By.XPATH, '//div[@aria-label="Message"]'),
]

# Selector for the "invalid number" / "phone not on WhatsApp" error popup
INVALID_NUMBER_SELECTORS = [
    (By.XPATH, '//div[contains(text(), "Phone number shared via url is invalid")]'),
    (By.XPATH, '//div[contains(@data-animate-modal-body, "true")]'),
]

def find_send_box(driver, timeout=25):
    """Try each known selector for the message input box."""
    for by, selector in SEND_BOX_SELECTORS:
        try:
            box = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            return box
        except TimeoutException:
            continue
    return None

def check_invalid_number(driver):
    """Return True if WhatsApp is showing a 'not on WhatsApp' error."""
    for by, selector in INVALID_NUMBER_SELECTORS:
        try:
            driver.find_element(by, selector)
            return True
        except Exception:
            continue
    return False

def dismiss_modal(driver):
    """Close any open error modal (press Escape)."""
    try:
        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(1)
    except Exception:
        pass

def send_message(driver, cleaned, message):
    """
    Navigate to the WA send URL, find the input box, and send.
    Returns True on success, False on failure.
    """
    encoded_message = urllib.parse.quote(message)
    url = f"https://web.whatsapp.com/send?phone={cleaned}&text={encoded_message}"

    driver.get(url)

    # Give the page a moment to start loading before we inspect it
    time.sleep(3)

    boxes = driver.find_elements(By.XPATH, '//div[@contenteditable="true"]')
    for b in boxes:
        print(b.get_attribute("outerHTML")[:200])

    # Check early for invalid number modal
    if check_invalid_number(driver):
        log(f"[SKIP] {cleaned} — not on WhatsApp (invalid number modal)")
        dismiss_modal(driver)
        return False

    box = find_send_box(driver, timeout=25)

    if box is None:
        log(f"[FAIL] {cleaned} — send box not found with any known selector")
        return False

    # Click to ensure focus, then wait for WhatsApp to fully settle
    try:
        box.click()
    except Exception:
        pass

    time.sleep(1.5)

    # Check once more for invalid number after the box search timeout
    if check_invalid_number(driver):
        log(f"[SKIP] {cleaned} — not on WhatsApp (post-load check)")
        dismiss_modal(driver)
        return False

    box.send_keys(Keys.ENTER)

    # Brief pause to let the send animation complete before moving on
    time.sleep(1)

    return True

def run(csv_file, phone_column, message, delay, profile_path):
    try:
        df = pd.read_csv(csv_file)
        log(f"[INFO] CSV loaded: {len(df)} rows")
    except Exception as e:
        log(f"[ERROR] Failed to load CSV: {e}")
        return

    if phone_column not in df.columns:
        log(f"[ERROR] Column '{phone_column}' not found. Available: {list(df.columns)}")
        return

    numbers = df[phone_column].dropna().astype(str).tolist()
    log(f"[INFO] Found {len(numbers)} phone numbers")

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if profile_path:
        options.add_argument(f"--user-data-dir={profile_path}")

    driver = webdriver.Chrome(options=options)
    driver.get("https://web.whatsapp.com")

    log("[WAIT] WhatsApp Web is open. Please scan the QR code.")
    log("[ACTION] Click 'QR Scanned – Continue' in the dashboard when ready.")

    if not wait_for_ready_signal():
        driver.quit()
        return

    log("[INFO] Starting to send messages...")

    success = []
    failed  = []
    skipped = []

    for number in numbers:
        cleaned = re.sub(r"\D", "", number)
        if not cleaned:
            log(f"[SKIP] Empty number from value: {number!r}")
            skipped.append(number)
            continue

        log(f"[SENDING] {cleaned}")

        try:
            ok = send_message(driver, cleaned, message)
            if ok:
                log(f"[OK] Sent to {cleaned}")
                success.append(cleaned)
            else:
                skipped.append(cleaned)
        except Exception as e:
            log(f"[FAIL] {number} — {e}")
            failed.append(number)

        time.sleep(int(delay))

    log(
        f"[DONE] Sent: {len(success)} | "
        f"Skipped (no WA): {len(skipped)} | "
        f"Failed: {len(failed)} | "
        f"Total: {len(numbers)}"
    )
    driver.quit()


if __name__ == "__main__":
    args = json.loads(sys.argv[1])
    run(
        args["csv_file"],
        args["phone_column"],
        args["message"],
        args["delay"],
        args.get("profile_path", "")
    )