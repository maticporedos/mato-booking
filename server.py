"""
server.py — Backend za frizerski booking

Zaganjanje:
    python3 server.py

Endpoints:
    GET  /api/taken?date=YYYY-MM-DD  → vrne zasedene termine
    POST /api/rezerviraj             → ustvari rezervacijo v Google Calendar
"""

from flask import Flask, request, jsonify, send_from_directory
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, date, timedelta
from pathlib import Path
import os

app = Flask(__name__)

CREDENTIALS_FILE = Path(__file__).parent.parent / "pt-automation" / "credentials.json"
# ID tvojega Google Calendarja — dobimo ga v naslednjem koraku
CALENDAR_ID = "matic.poredos@gmail.com"

TRAJANJE_MIN = 40  # minutr na stranko

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def calendar_service():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)

def zasedeni_termini(datum_str):
    """Vrne seznam zasedenih časov (HH:MM) za določen datum."""
    try:
        d = date.fromisoformat(datum_str)
        zacetek = datetime(d.year, d.month, d.day, 0, 0, 0).isoformat() + "Z"
        konec    = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat() + "Z"

        service = calendar_service()
        events = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=zacetek,
            timeMax=konec,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        zasedeni = []
        for event in events.get("items", []):
            start = event.get("start", {}).get("dateTime", "")
            if start:
                cas = datetime.fromisoformat(start.replace("Z", "+00:00"))
                zasedeni.append(f"{cas.hour:02d}:{cas.minute:02d}")
        return zasedeni
    except Exception as e:
        print(f"Napaka pri branju terminov: {e}")
        return []

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/taken")
def taken():
    datum = request.args.get("date", "")
    if not datum:
        return jsonify([])
    return jsonify(zasedeni_termini(datum))

@app.route("/api/rezerviraj", methods=["POST"])
def rezerviraj():
    data = request.get_json()
    ime      = data.get("ime", "").strip()
    priimek  = data.get("priimek", "").strip()
    telefon  = data.get("telefon", "").strip()
    datum    = data.get("datum", "").strip()
    cas      = data.get("cas", "").strip()
    storitev = data.get("storitev", "Moško striženje").strip()

    if not all([ime, priimek, telefon, datum, cas]):
        return jsonify({"error": "Manjkajoči podatki"}), 400

    try:
        d = date.fromisoformat(datum)
        ura, minuta = map(int, cas.split(":"))
        zacetek = datetime(d.year, d.month, d.day, ura, minuta)
        konec   = zacetek + timedelta(minutes=TRAJANJE_MIN)

        # Preveri da termin ni že zaseden
        zasedeni = zasedeni_termini(datum)
        if cas in zasedeni:
            return jsonify({"error": "Ta termin je že zaseden. Izberi drugega."}), 409

        service = calendar_service()
        event = {
            "summary": f"✂ {ime} {priimek} — {storitev}",
            "description": f"Stranka: {ime} {priimek}\nTelefon: {telefon}\nStoritev: {storitev}",
            "start": {
                "dateTime": zacetek.isoformat(),
                "timeZone": "Europe/Ljubljana",
            },
            "end": {
                "dateTime": konec.isoformat(),
                "timeZone": "Europe/Ljubljana",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "popup", "minutes": 10},
                ]
            }
        }

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

        print(f"✅ Rezervacija: {ime} {priimek} — {datum} ob {cas}")
        return jsonify({"ok": True})

    except Exception as e:
        print(f"❌ Napaka: {e}")
        return jsonify({"error": "Napaka pri rezervaciji. Poskusi znova."}), 500

if __name__ == "__main__":
    print("🚀 Booking strežnik teče na http://localhost:5000")
    app.run(debug=True, port=8080)
