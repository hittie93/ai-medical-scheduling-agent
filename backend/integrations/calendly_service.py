class CalendlyService:
    """Minimal Calendly service stub for available slots."""

    def get_available_slots(self, doctor: str, location: str, duration_minutes: int):
        # Return a few mock slots for testing
        return [
            {"date": "2025-09-10", "time": "09:00"},
            {"date": "2025-09-10", "time": "11:00"},
            {"date": "2025-09-11", "time": "14:30"},
            {"date": "2025-09-12", "time": "16:00"},
            {"date": "2025-09-13", "time": "10:15"},
        ]


"""
Calendly Integration Service for Medical Appointment Scheduling
Handles calendar slot management, booking, and availability checking
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import pandas as pd
from pathlib import Path
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class CalendlyService:
    """
    Calendly API wrapper for managing medical appointments
    Implements smart scheduling with 60min (new) and 30min (returning) patient logic
    """
    
    def __init__(self, api_key: Optional[str] = None, use_mock: bool = True):
        """
        Initialize Calendly service
        
        Args:
            api_key: Calendly API key (optional for mock mode)
            use_mock: Use mock data for testing without actual API
        """
        # Load environment and API key
        load_dotenv()
        self.api_key = api_key or os.getenv('CALENDLY_API_KEY')
        self.base_url = "https://api.calendly.com"
        # If API key is present, prefer real API; otherwise fallback to mock
        self.use_mock = use_mock if api_key is None else (False if self.api_key else True)
        
        # Mock data storage
        self.mock_calendar_file = Path("data/doctor_schedules.json")
        self.appointments_file = Path("data/appointments.json")
        self.doctor_schedules_xlsx = Path("data/appointments.xlsx")  # Use separate file for appointments
        
        # Initialize mock data if needed
        if self.use_mock:
            self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock calendar data for testing"""
        if not self.mock_calendar_file.exists():
            # Generate synthetic doctor schedules
            mock_schedules = self._generate_mock_schedules()
            self.mock_calendar_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.mock_calendar_file, 'w') as f:
                json.dump(mock_schedules, f, indent=2, default=str)
        
        if not self.appointments_file.exists():
            with open(self.appointments_file, 'w') as f:
                json.dump([], f)
    
    def _generate_mock_schedules(self) -> Dict:
        """Generate synthetic doctor schedules with availability"""
        doctors = [
            {"id": "dr_sharma", "name": "Dr. Sharma", "specialty": "General Medicine"},
            {"id": "dr_iyer", "name": "Dr. Iyer", "specialty": "Cardiology"},
            {"id": "dr_mehta", "name": "Dr. Mehta", "specialty": "Orthopedics"},
            {"id": "dr_kapoor", "name": "Dr. Kapoor", "specialty": "Dermatology"},
            {"id": "dr_reddy", "name": "Dr. Reddy", "specialty": "Pediatrics"},
        ]
        
        schedules = {}
        start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        
        for doctor in doctors:
            doctor_schedule = {
                "doctor_info": doctor,
                "available_slots": []
            }
            
            # Generate slots for next 14 days
            for day_offset in range(14):
                current_date = start_date + timedelta(days=day_offset)
                
                # Skip weekends
                if current_date.weekday() >= 5:
                    continue
                
                # Generate hourly slots from 9 AM to 5 PM
                for hour in range(9, 17):
                    for minute in [0, 30]:  # 30-minute slots
                        slot_time = current_date.replace(hour=hour, minute=minute)
                        
                        # Randomly mark some slots as unavailable (20% chance)
                        import random
                        is_available = random.random() > 0.2
                        
                        doctor_schedule["available_slots"].append({
                            "datetime": slot_time.isoformat(),
                            "duration_minutes": 30,
                            "is_available": is_available
                        })
            
            schedules[doctor["id"]] = doctor_schedule
        
        return schedules
    
    def get_available_slots(self, 
                           doctor_id: str, 
                           date_from: Optional[datetime] = None,
                           date_to: Optional[datetime] = None,
                           duration_minutes: int = 30) -> List[Dict]:
        """
        Get available appointment slots for a doctor
        
        Args:
            doctor_id: Doctor identifier
            date_from: Start date for slot search (default: today)
            date_to: End date for slot search (default: 2 weeks from today)
            duration_minutes: Required slot duration (30 for returning, 60 for new patients)
        
        Returns:
            List of available time slots
        """
        if not date_from:
            date_from = datetime.now()
        if not date_to:
            date_to = date_from + timedelta(days=14)
        
        if self.use_mock:
            return self._get_mock_available_slots(doctor_id, date_from, date_to, duration_minutes)
        else:
            return self._get_api_available_slots(doctor_id, date_from, date_to, duration_minutes)
    
    def _get_mock_available_slots(self, doctor_id: str, date_from: datetime, 
                                  date_to: datetime, duration_minutes: int) -> List[Dict]:
        """Get available slots using Scheduler working hours and check existing bookings."""
        # Import here to avoid circular imports
        from backend.schedular import Scheduler, PatientType

        scheduler = Scheduler()
        # Map our doctor_id to scheduler's ids if needed (assume same ids in create_sample_schedules)
        sched_doctor_id = doctor_id

        # Load existing bookings from Excel
        existing_bookings = self._load_existing_bookings()

        # Build a list of dates from date_from to date_to
        day = date_from
        collected: List[Dict] = []
        while day <= date_to and len(collected) < 50:
            # For each day, find slots based on duration (derive patient type for duration)
            ptype = PatientType.NEW if duration_minutes >= 60 else PatientType.RETURNING
            slots = scheduler.find_available_slots(sched_doctor_id, day, ptype, num_slots=10)
            
            for s in slots:
                # Check if this slot is already booked
                doctor_name = scheduler.doctors.get(sched_doctor_id).doctor_name if sched_doctor_id in scheduler.doctors else 'Doctor'
                slot_key = f"{doctor_name}_{s.start_time.strftime('%Y-%m-%d')}_{s.start_time.strftime('%H:%M')}"
                
                if slot_key in existing_bookings and not existing_bookings[slot_key]['available']:
                    # Slot is already booked, skip it
                    continue
                
                # Add to available slots
                collected.append({
                    'datetime': s.start_time.isoformat(),
                    'duration_minutes': duration_minutes,
                    'doctor_id': doctor_id,
                    'doctor_name': doctor_name,
                    'type': '60min_new_patient' if duration_minutes >= 60 else '30min_returning'
                })
                
                # Prefill Excel with available slots (available=True) if not already present
                try:
                    dt = s.start_time
                    self._prefill_available_slot(
                        doctor=doctor_name,
                        dt=dt,
                        location=scheduler.doctors.get(sched_doctor_id).location if sched_doctor_id in scheduler.doctors else 'Main Clinic'
                    )
                except Exception:
                    pass
                if len(collected) >= 50:
                    break
            day = day + timedelta(days=1)

        return collected[:20]
    
    def _load_existing_bookings(self) -> Dict[str, Dict]:
        """Load existing bookings from Excel file to check availability."""
        existing_bookings = {}
        
        if not self.doctor_schedules_xlsx.exists():
            return existing_bookings
            
        try:
            df = pd.read_excel(self.doctor_schedules_xlsx)
            # Check if the file has the expected columns
            expected_columns = ['doctor', 'date', 'time', 'available', 'patient_name', 'patient_email']
            if not all(col in df.columns for col in expected_columns):
                logger.warning(f"Excel file doesn't have expected columns: {df.columns.tolist()}")
                return existing_bookings
                
            for _, row in df.iterrows():
                doctor = row.get('doctor', '')
                date = row.get('date', '')
                time = row.get('time', '')
                available = row.get('available', True)
                patient_name = row.get('patient_name', '')
                patient_email = row.get('patient_email', '')
                
                if doctor and date and time:
                    slot_key = f"{doctor}_{date}_{time}"
                    existing_bookings[slot_key] = {
                        'available': available,
                        'patient_name': patient_name,
                        'patient_email': patient_email
                    }
        except Exception as e:
            logger.warning(f"Failed to load existing bookings: {e}")
            
        return existing_bookings
    
    def _get_api_available_slots(self, doctor_id: str, date_from: datetime,
                                 date_to: datetime, duration_minutes: int) -> List[Dict]:
        """Get available slots from actual Calendly API"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # Note: Calendly API specifics depend on event types/organization. This uses a generic availability endpoint style.
        params = {
            'min_start_time': date_from.isoformat(),
            'max_start_time': date_to.isoformat(),
            'event_type_uuid': doctor_id,
        }

        try:
            response = requests.get(
                f"{self.base_url}/availability_schedules",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            # Parse Calendly response and format slots
            slots = []
            # This parsing is illustrative; adapt as per actual Calendly response
            for sched in data.get('collection', []):
                for interval in sched.get('intervals', []):
                    start = interval.get('start_time') or interval.get('start')
                    if not start:
                        continue
                    slots.append({
                        'datetime': start,
                        'duration_minutes': duration_minutes,
                        'doctor_id': doctor_id,
                        'doctor_name': sched.get('name', 'Doctor'),
                        'booking_url': sched.get('scheduling_url', ''),
                        'location': 'Main Clinic'
                    })
            return slots
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Calendly API error: {e}")
            # Fallback to mock data
            return self._get_mock_available_slots(doctor_id, date_from, date_to, duration_minutes)
    
    def book_appointment(self, 
                        patient_data: Dict,
                        doctor_id: str,
                        datetime_slot: str,
                        duration_minutes: int,
                        appointment_type: str) -> Dict[str, Any]:
        """
        Book an appointment slot
        
        Args:
            patient_data: Patient information (name, DOB, contact, insurance)
            doctor_id: Doctor identifier
            datetime_slot: ISO format datetime string
            duration_minutes: Appointment duration (30 or 60)
            appointment_type: 'new_patient' or 'returning_patient'
        
        Returns:
            Booking confirmation with appointment details
        """
        if self.use_mock:
            return self._book_mock_appointment(patient_data, doctor_id, 
                                              datetime_slot, duration_minutes, 
                                              appointment_type)
        else:
            return self._book_api_appointment(patient_data, doctor_id,
                                             datetime_slot, duration_minutes,
                                             appointment_type)
    
    def _book_mock_appointment(self, patient_data: Dict, doctor_id: str,
                               datetime_slot: str, duration_minutes: int,
                               appointment_type: str) -> Dict[str, Any]:
        """Book appointment in mock system"""
        # Load existing appointments
        with open(self.appointments_file, 'r') as f:
            appointments = json.load(f)
        
        # Generate appointment ID
        appointment_id = f"APT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(appointments)+1:04d}"
        
        # Create appointment record
        appointment = {
            'appointment_id': appointment_id,
            'patient_data': patient_data,
            'doctor_id': doctor_id,
            'datetime': datetime_slot,
            'duration_minutes': duration_minutes,
            'appointment_type': appointment_type,
            'status': 'confirmed',
            'booked_at': datetime.now().isoformat(),
            'reminders_sent': [],
            'forms_sent': False,
            'confirmation_sent': False
        }
        
        # Add to appointments list
        appointments.append(appointment)
        
        # Save appointments
        with open(self.appointments_file, 'w') as f:
            json.dump(appointments, f, indent=2, default=str)
        
        # Get doctor info
        with open(self.mock_calendar_file, 'r') as f:
            schedules = json.load(f)
        doctor_info = schedules.get(doctor_id, {}).get('doctor_info', {})
        
        return {
            'success': True,
            'appointment_id': appointment_id,
            'confirmation_message': f"Appointment confirmed for {patient_data.get('name')}",
            'details': {
                'datetime': datetime_slot,
                'duration': f"{duration_minutes} minutes",
                'doctor': doctor_info.get('name', 'Doctor'),
                'type': appointment_type,
                'location': 'Main Clinic - 123 Medical Center Dr.',
                'instructions': 'Please arrive 15 minutes early for check-in.'
            }
        }
    
    def _book_api_appointment(self, patient_data: Dict, doctor_id: str,
                             datetime_slot: str, duration_minutes: int,
                             appointment_type: str) -> Dict[str, Any]:
        """Book appointment via Calendly API"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'event_type_uuid': doctor_id,
            'start_time': datetime_slot,
            'invitee': {
                'name': patient_data.get('name'),
                'email': patient_data.get('email'),
            },
            'questions_and_answers': [
                {'question': 'Patient Type', 'answer': appointment_type},
                {'question': 'Insurance', 'answer': patient_data.get('insurance_carrier', 'N/A')}
            ]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/scheduled_events",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            result = {
                'success': True,
                'appointment_id': data.get('uri', '').split('/')[-1],
                'confirmation_message': f"Appointment booked successfully",
                'details': {
                    'datetime': datetime_slot,
                    'duration': f"{duration_minutes} minutes",
                    'doctor_id': doctor_id,
                    'type': appointment_type,
                    'calendly_link': data.get('invitee_uri', '')
                }
            }
            # Log booking to Excel
            self._log_booking_to_excel(
                doctor=patient_data.get('doctor_name', 'Doctor'),
                dt=datetime.fromisoformat(datetime_slot),
                location=patient_data.get('location', 'Main Clinic'),
                patient_name=patient_data.get('name', ''),
                patient_email=patient_data.get('email', ''),
            )
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Calendly booking error: {e}")
            # Fallback to mock booking
            return self._book_mock_appointment(patient_data, doctor_id,
                                              datetime_slot, duration_minutes,
                                              appointment_type)

    # Public API per requirements
    def book_slot(self, slot: Dict[str, Any], patient_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Book a provided slot and log the appointment to Excel.
        Slot must contain at least 'datetime' (ISO) and 'doctor_id'.
        """
        dt_iso = slot.get('datetime') if isinstance(slot.get('datetime'), str) else (
            slot.get('datetime').isoformat() if slot.get('datetime') else None)
        result = self.book_appointment(
            patient_data={
                'name': patient_info.get('name'),
                'email': patient_info.get('email'),
                'insurance_carrier': patient_info.get('insurance_carrier'),
                'doctor_name': patient_info.get('doctor_name'),
                'location': patient_info.get('location'),
            },
            doctor_id=slot.get('doctor_id', ''),
            datetime_slot=dt_iso,
            duration_minutes=slot.get('duration_minutes', 30),
            appointment_type=patient_info.get('appointment_type', 'returning_patient')
        )
        # Ensure Excel is updated in mock path as well
        self._log_booking_to_excel(
            doctor=patient_info.get('doctor_name', 'Doctor'),
            dt=datetime.fromisoformat(dt_iso),
            location=patient_info.get('location', 'Main Clinic'),
            patient_name=patient_info.get('name', ''),
            patient_email=patient_info.get('email', ''),
        )
        return result

    def _log_booking_to_excel(self, doctor: str, dt: datetime, location: str,
                              patient_name: str, patient_email: str):
        """Append or update booking in doctor_schedules.xlsx per requirements."""
        self.doctor_schedules_xlsx.parent.mkdir(parents=True, exist_ok=True)
        columns = [
            'doctor', 'date', 'time', 'location', 'available', 'patient_name', 'patient_email'
        ]
        if self.doctor_schedules_xlsx.exists():
            try:
                df = pd.read_excel(self.doctor_schedules_xlsx)
            except Exception:
                df = pd.DataFrame(columns=columns)
        else:
            df = pd.DataFrame(columns=columns)

        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H:%M')
        match = (df['doctor'] == doctor) & (df['date'] == date_str) & (df['time'] == time_str)
        if df.empty or not match.any():
            new_row = {
                'doctor': doctor,
                'date': date_str,
                'time': time_str,
                'location': location,
                'available': False,
                'patient_name': patient_name,
                'patient_email': patient_email,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df.loc[match, ['available', 'patient_name', 'patient_email', 'location']] = [False, patient_name, patient_email, location]

        df.to_excel(self.doctor_schedules_xlsx, index=False)
    
    def _doctor_id_to_name(self, doctor_id):
        mapping = {
            "dr_sharma": "Dr. Sharma",
            "dr_iyer": "Dr. Iyer",
            "dr_mehta": "Dr. Mehta",
            "dr_kapoor": "Dr. Kapoor",
            "dr_reddy": "Dr. Reddy"
        }
        return mapping.get(doctor_id, doctor_id)


    def _prefill_available_slot(self, doctor: str, dt: datetime, location: str):
        """Write available=True row for a slot if not present."""
        self.doctor_schedules_xlsx.parent.mkdir(parents=True, exist_ok=True)
        columns = ['doctor', 'date', 'time', 'location', 'available', 'patient_name', 'patient_email']
        if self.doctor_schedules_xlsx.exists():
            try:
                df = pd.read_excel(self.doctor_schedules_xlsx)
            except Exception:
                df = pd.DataFrame(columns=columns)
        else:
            df = pd.DataFrame(columns=columns)

        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H:%M')
        match = (df['doctor'] == doctor) & (df['date'] == date_str) & (df['time'] == time_str)
        if df.empty or not match.any():
            new_row = {
                'doctor': doctor,
                'date': date_str,
                'time': time_str,
                'location': location,
                'available': True,
                'patient_name': '',
                'patient_email': '',
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_excel(self.doctor_schedules_xlsx, index=False)
    
    def cancel_appointment(self, appointment_id: str, reason: str = "") -> Dict[str, Any]:
        """
        Cancel an appointment
        
        Args:
            appointment_id: Appointment identifier
            reason: Cancellation reason
        
        Returns:
            Cancellation confirmation
        """
        if self.use_mock:
            # Update appointment status in mock data
            with open(self.appointments_file, 'r') as f:
                appointments = json.load(f)
            
            for apt in appointments:
                if apt['appointment_id'] == appointment_id:
                    apt['status'] = 'cancelled'
                    apt['cancellation_reason'] = reason
                    apt['cancelled_at'] = datetime.now().isoformat()
                    
                    with open(self.appointments_file, 'w') as f:
                        json.dump(appointments, f, indent=2, default=str)
                    
                    return {
                        'success': True,
                        'message': f"Appointment {appointment_id} cancelled successfully",
                        'reason': reason
                    }
            
            return {
                'success': False,
                'message': f"Appointment {appointment_id} not found"
            }
        else:
            # Cancel via Calendly API
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/scheduled_events/{appointment_id}/cancellation",
                    headers=headers,
                    json={'reason': reason}
                )
                response.raise_for_status()
                
                return {
                    'success': True,
                    'message': f"Appointment cancelled successfully",
                    'reason': reason
                }
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Calendly cancellation error: {e}")
                return {
                    'success': False,
                    'message': f"Failed to cancel appointment: {str(e)}"
                }
    
    def get_appointment_details(self, appointment_id: str) -> Optional[Dict]:
        """Get details of a specific appointment"""
        if self.use_mock:
            with open(self.appointments_file, 'r') as f:
                appointments = json.load(f)
            
            for apt in appointments:
                if apt['appointment_id'] == appointment_id:
                    return apt
            return None
        else:
            # Fetch from Calendly API
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            try:
                response = requests.get(
                    f"{self.base_url}/scheduled_events/{appointment_id}",
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Calendly fetch error: {e}")
                return None