"""
Flask webhook to process incoming SMS replies from Twilio.
Endpoint: /sms-reply (POST)

If incoming body contains 'cancel', find the latest appointment for the sender's phone
in data/appointments.xlsx and reopen the slot via backend.remainders.ReminderSystem.reopen_slot().
"""

from flask import Flask, request, jsonify
from pathlib import Path
from datetime import datetime
import pandas as pd

try:
    # When running as a module
    from backend.remainders import ReminderSystem
except ModuleNotFoundError:
    # Fallback for direct execution
    from remainders import ReminderSystem

app = Flask(__name__)


def _normalize_phone(phone: str) -> str:
    if not phone:
        return ''
    return ''.join(ch for ch in phone if ch.isdigit() or ch == '+')


@app.post('/sms-reply')
def sms_reply():
    from_number = request.form.get('From') or request.json.get('From') if request.is_json else None
    body = request.form.get('Body') or request.json.get('Body') if request.is_json else ''

    if not from_number:
        return jsonify({"status": "error", "message": "Missing From number"}), 400

    normalized_from = _normalize_phone(from_number)
    body_lower = (body or '').lower()

    if 'cancel' not in body_lower:
        return jsonify({"status": "ignored", "message": "No cancellation keyword found"}), 200

    # Load appointments.xlsx and find latest by patient_phone (if present)
    xlsx_path = Path('data/appointments.xlsx')
    if not xlsx_path.exists():
        return jsonify({"status": "error", "message": "No appointments file found"}), 404

    try:
        df = pd.read_excel(xlsx_path)
    except Exception:
        return jsonify({"status": "error", "message": "Failed to read appointments file"}), 500

    # Ensure patient_phone column exists; if not, attempt loose matching on any phone-like column
    phone_col = 'patient_phone' if 'patient_phone' in df.columns else None
    if not phone_col:
        for c in df.columns:
            if 'phone' in c.lower():
                phone_col = c
                break

    if not phone_col:
        return jsonify({"status": "error", "message": "No phone column in appointments"}), 500

    # Filter and pick latest (by created/ date+time)
    subset = df[df[phone_col].astype(str).str.replace('[^0-9+]', '', regex=True) == normalized_from]
    if subset.empty:
        return jsonify({"status": "error", "message": "No matching appointment for this phone"}), 404

    # Determine latest row
    if 'created_at' in subset.columns:
        subset_sorted = subset.sort_values('created_at')
    elif {'date', 'time'}.issubset(subset.columns):
        subset_sorted = subset.copy()
        try:
            subset_sorted['__dt'] = pd.to_datetime(subset_sorted['date'] + ' ' + subset_sorted['time'])
            subset_sorted = subset_sorted.sort_values('__dt')
        except Exception:
            subset_sorted = subset
    else:
        subset_sorted = subset

    last = subset_sorted.iloc[-1]
    doctor = str(last.get('doctor', ''))
    date = str(last.get('date', ''))
    time = str(last.get('time', ''))
    appt_id = str(last.get('appointment_id', ''))

    # Reopen slot via ReminderSystem helper
    rs = ReminderSystem()
    ok = rs.reopen_slot(appointment_id=appt_id or datetime.now().strftime('%Y%m%d%H%M%S'),
                        doctor=doctor, date=date, time=time, channel="sms")

    if ok:
        return jsonify({"status": "ok", "message": "Your appointment has been cancelled and the slot reopened."}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to cancel appointment."}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)


