"""
Central cancellation logging system.
Records all appointment cancellations with details and channel information.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def log_cancellation(
    appointment_id: str,
    patient_name: str,
    patient_email: str,
    patient_phone: str,
    doctor: str,
    date: str,
    time: str,
    channel: str
) -> bool:
    """
    Log a cancellation to the central cancellation log.
    
    Args:
        appointment_id: Unique appointment identifier
        patient_name: Patient's full name
        patient_email: Patient's email address
        patient_phone: Patient's phone number
        doctor: Doctor's name
        date: Appointment date (YYYY-MM-DD format)
        time: Appointment time (HH:MM format)
        channel: How the cancellation was triggered (sms, email, reminder-auto, etc.)
    
    Returns:
        True if logged successfully, False otherwise
    """
    try:
        # Ensure data directory exists
        log_path = Path("data/cancellations_log.json")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing cancellations or create empty list
        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    cancellations = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                cancellations = []
        else:
            cancellations = []
        
        # Create new cancellation entry
        cancellation_entry = {
            "appointment_id": appointment_id,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "patient_phone": patient_phone,
            "doctor": doctor,
            "date": date,
            "time": time,
            "channel": channel,
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Append to list
        cancellations.append(cancellation_entry)
        
        # Write back to file
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(cancellations, f, indent=2, ensure_ascii=False)
        
        # Log to console
        logger.info(f"Logged cancellation for appointment_id={appointment_id} channel={channel}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to log cancellation: {e}")
        return False


def get_cancellation_stats() -> dict:
    """
    Get statistics about cancellations.
    
    Returns:
        Dictionary with cancellation statistics
    """
    try:
        log_path = Path("data/cancellations_log.json")
        if not log_path.exists():
            return {
                "total_cancellations": 0,
                "by_channel": {},
                "by_doctor": {},
                "recent_cancellations": []
            }
        
        with open(log_path, 'r', encoding='utf-8') as f:
            cancellations = json.load(f)
        
        # Calculate statistics
        total = len(cancellations)
        by_channel = {}
        by_doctor = {}
        
        for cancellation in cancellations:
            channel = cancellation.get('channel', 'unknown')
            doctor = cancellation.get('doctor', 'unknown')
            
            by_channel[channel] = by_channel.get(channel, 0) + 1
            by_doctor[doctor] = by_doctor.get(doctor, 0) + 1
        
        # Get recent cancellations (last 10)
        recent = sorted(cancellations, key=lambda x: x.get('cancelled_at', ''), reverse=True)[:10]
        
        return {
            "total_cancellations": total,
            "by_channel": by_channel,
            "by_doctor": by_doctor,
            "recent_cancellations": recent
        }
        
    except Exception as e:
        logger.error(f"Failed to get cancellation stats: {e}")
        return {
            "total_cancellations": 0,
            "by_channel": {},
            "by_doctor": {},
            "recent_cancellations": []
        }


if __name__ == "__main__":
    # Test the cancellation logging
    test_result = log_cancellation(
        appointment_id="TEST123",
        patient_name="Test Patient",
        patient_email="test@example.com",
        patient_phone="+1234567890",
        doctor="Dr. Test",
        date="2024-01-15",
        time="10:00",
        channel="test"
    )
    
    if test_result:
        print("✅ Cancellation logging test successful")
        stats = get_cancellation_stats()
        print(f"📊 Total cancellations: {stats['total_cancellations']}")
    else:
        print("❌ Cancellation logging test failed")
