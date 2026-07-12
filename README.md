# Loop Dashboard

A minimal desktop dashboard for Loop Developers' outreach toolkit.

## Project Structure

```
loop_dashboard/
├── server.py                  ← Flask backend (run this)
├── start.bat                  ← Windows launcher
├── requirements.txt
├── scripts/
│   ├── gmaps_scraper.py       ← Google Maps lead scraper
│   ├── bulk_email.py          ← Bulk email sender
│   └── bulk_whatsapp.py       ← WhatsApp Web automation
└── frontend/
    └── dist/
        └── index.html         ← The UI (no build step needed)
```

## Setup

### 1. Install Python dependencies
```
pip install -r requirements.txt
playwright install chromium
```

### 2. Place your CSV files
Put your `test.csv` or leads CSV in the same folder as `server.py` (or use an absolute path in the UI).

### 3. Run the dashboard
**Windows:**
```
start.bat
```
or manually:
```
python server.py
```

### 4. Open in browser
```
http://localhost:5000
```

---

## Tools

### 🗺️ Maps Scraper
- Enter a search query (e.g. "restaurants in New York, USA")
- Set how many results to collect
- Scrapes Google Maps + business websites for emails
- Saves to a CSV file

### ✉️ Bulk Email
- Fill SMTP settings (pre-filled for Hostinger)
- Load a CSV with an "Email" column
- Edit subject + message body
- Live progress in the console

### 💬 Bulk WhatsApp
- Provide a CSV with a "Phone" column
- Chrome will open with WhatsApp Web
- Scan QR code, then press ENTER in the terminal
- Messages sent automatically with configurable delay

---

## Notes
- The WhatsApp tool requires pressing ENTER in the terminal window after QR login — this is a one-time step per Chrome profile.
- Keep your Chrome profile path consistent across runs to avoid re-scanning the QR code.
- All output logs stream live into the console panel in the UI.
