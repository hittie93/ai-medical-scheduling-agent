"""
SMS Service for appointment reminders using Twilio
Handles 3-stage reminder system with confirmation tracking
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioException
except Exception:  # Twilio not installed or import failed
    Client = None  # type: ignore
    class TwilioException(Exception):
        pass
import logging
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReminderStage(Enum):
    """Reminder stages with specific actions"""
    FIRST = "regular"  # Standard reminder
    SECOND = "form_check"  # Check if forms are filled
    THIRD = "confirmation_check"  # Confirm attendance or get cancellation reason

@dataclass
class SMSReminder:
    """SMS reminder data structure"""
    patient_phone: str
    patient_name: str
    appointment_date: datetime
    appointment_time: str
    doctor_name: str
    stage: ReminderStage
    appointment_id: str
    forms_completed: bool = False
    visit_confirmed: Optional[bool] = None
    cancellation_reason: Optional[str] = None

class SMSService:
    """
    Handles SMS communications for appointment reminders
    Implements 3-stage reminder system as per requirements
    """
    
    def __init__(self, account_sid: Optional[str] = None, 
                 auth_token: Optional[str] = None,
                 from_number: Optional[str] = None,
                 mock_mode: bool = False):
        """
        Initialize SMS service
        
        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Twilio phone number
            mock_mode: If True, simulate SMS sending without actual API calls
        """
        self.mock_mode = mock_mode
        
        if not mock_mode and Client is not None:
            self.account_sid = account_sid or os.environ.get('TWILIO_ACCOUNT_SID')
            self.auth_token = auth_token or os.environ.get('TWILIO_AUTH_TOKEN')
            self.from_number = from_number or os.environ.get('TWILIO_PHONE_NUMBER')
            
            if not all([self.account_sid, self.auth_token, self.from_number]):
                logger.warning("Twilio credentials not found. Running in mock mode.")
                self.mock_mode = True
            else:
                try:
                    self.client = Client(self.account_sid, self.auth_token)
                except Exception as e:
                    logger.error(f"Failed to initialize Twilio client: {e}")
                    self.mock_mode = True
        else:
            if Client is None:
                logger.warning("Twilio SDK not available. SMSService running in mock mode.")
        
        # Track sent reminders
        self.sent_reminders: Dict[str, List[Dict]] = {}
        
    def send_reminder(self, reminder: SMSReminder) -> Tuple[bool, str]:
        """
        Send SMS reminder based on stage
        
        Args:
            reminder: SMSReminder object with appointment details
            
        Returns:
            Tuple of (success, message_sid or error message)
        """
        message = self._compose_message(reminder)
        
        if self.mock_mode:
            return self._mock_send(reminder, message)
        
        try:
            message_obj = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=reminder.patient_phone
            )
            
            # Track the reminder
            self._track_reminder(reminder, message_obj.sid, message)
            
            logger.info(f"SMS sent successfully to {reminder.patient_phone}: {message_obj.sid}")
            return True, message_obj.sid
            
        except TwilioException as e:
            logger.error(f"Failed to send SMS: {e}")
            return False, str(e)
    
    def _compose_message(self, reminder: SMSReminder) -> str:
        """
        Compose SMS message based on reminder stage
        
        Args:
            reminder: SMSReminder object
            
        Returns:
            Composed SMS message
        """
        base_info = (f"Hi {reminder.patient_name}, reminder for your appointment with "
                    f"Dr. {reminder.doctor_name} on {reminder.appointment_date.strftime('%B %d, %Y')} "
                    f"at {reminder.appointment_time}.")
        
        if reminder.stage == ReminderStage.FIRST:
            # Regular reminder
            message = f"{base_info} Please arrive 15 minutes early. Reply YES to confirm."
            
        elif reminder.stage == ReminderStage.SECOND:
            # Form check reminder
            if not reminder.forms_completed:
                message = (f"{base_info} Please complete your intake forms sent via email. "
                          f"Reply FORMS to confirm completion or HELP if you need assistance.")
            else:
                message = (f"{base_info} Thank you for completing your forms. "
                          f"Reply YES to confirm your attendance.")
                
        elif reminder.stage == ReminderStage.THIRD:
            # Final confirmation reminder
            message = (f"FINAL REMINDER: {base_info} "
                      f"Reply YES to confirm, or CANCEL followed by reason if you cannot attend. "
                      f"No-shows may incur charges.")
        
        return message
    
    def _mock_send(self, reminder: SMSReminder, message: str) -> Tuple[bool, str]:
        """
        Simulate SMS sending in mock mode
        
        Args:
            reminder: SMSReminder object
            message: SMS message content
            
        Returns:
            Tuple of (True, mock_message_id)
        """
        mock_sid = f"MOCK_{datetime.now().timestamp()}_{reminder.appointment_id}"
        
        # Track the reminder
        self._track_reminder(reminder, mock_sid, message)
        
        logger.info(f"[MOCK MODE] SMS would be sent to {reminder.patient_phone}:")
        logger.info(f"[MOCK MODE] Message: {message}")
        logger.info(f"[MOCK MODE] Mock SID: {mock_sid}")
        
        return True, mock_sid
    
    def _track_reminder(self, reminder: SMSReminder, message_sid: str, message_content: str):
        """
        Track sent reminders for reporting
        
        Args:
            reminder: SMSReminder object
            message_sid: Twilio message SID or mock ID
            message_content: Actual message sent
        """
        if reminder.appointment_id not in self.sent_reminders:
            self.sent_reminders[reminder.appointment_id] = []
        
        self.sent_reminders[reminder.appointment_id].append({
            'timestamp': datetime.now().isoformat(),
            'stage': reminder.stage.value,
            'message_sid': message_sid,
            'phone': reminder.patient_phone,
            'message': message_content,
            'forms_completed': reminder.forms_completed,
            'visit_confirmed': reminder.visit_confirmed
        })
    
    def send_bulk_reminders(self, reminders: List[SMSReminder]) -> Dict[str, Tuple[bool, str]]:
        """
        Send multiple reminders in bulk
        
        Args:
            reminders: List of SMSReminder objects
            
        Returns:
            Dictionary mapping appointment_id to (success, message_sid/error)
        """
        results = {}
        
        for reminder in reminders:
            success, message_info = self.send_reminder(reminder)
            results[reminder.appointment_id] = (success, message_info)
            
            # Add delay to avoid rate limiting
            if not self.mock_mode and len(reminders) > 1:
                import time
                time.sleep(1)  # 1 second delay between messages
        
        return results
    
    def schedule_reminders(self, appointment_date: datetime, 
                          appointment_id: str,
                          patient_phone: str,
                          patient_name: str,
                          doctor_name: str,
                          appointment_time: str) -> List[Dict]:
        """
        Schedule 3 reminders for an appointment
        
        Args:
            appointment_date: Date of appointment
            appointment_id: Unique appointment ID
            patient_phone: Patient's phone number
            patient_name: Patient's name
            doctor_name: Doctor's name
            appointment_time: Time of appointment
            
        Returns:
            List of scheduled reminder details
        """
        scheduled = []
        
        # First reminder: 48 hours before
        first_reminder_time = appointment_date - timedelta(hours=48)
        scheduled.append({
            'appointment_id': appointment_id,
            'stage': ReminderStage.FIRST,
            'scheduled_time': first_reminder_time,
            'patient_phone': patient_phone,
            'patient_name': patient_name,
            'doctor_name': doctor_name,
            'appointment_time': appointment_time
        })
        
        # Second reminder: 24 hours before (form check)
        second_reminder_time = appointment_date - timedelta(hours=24)
        scheduled.append({
            'appointment_id': appointment_id,
            'stage': ReminderStage.SECOND,
            'scheduled_time': second_reminder_time,
            'patient_phone': patient_phone,
            'patient_name': patient_name,
            'doctor_name': doctor_name,
            'appointment_time': appointment_time
        })
        
        # Third reminder: 2 hours before (final confirmation)
        third_reminder_time = appointment_date - timedelta(hours=2)
        scheduled.append({
            'appointment_id': appointment_id,
            'stage': ReminderStage.THIRD,
            'scheduled_time': third_reminder_time,
            'patient_phone': patient_phone,
            'patient_name': patient_name,
            'doctor_name': doctor_name,
            'appointment_time': appointment_time
        })
        
        logger.info(f"Scheduled 3 reminders for appointment {appointment_id}")
        return scheduled
    
    def process_sms_response(self, from_phone: str, message_body: str, 
                            appointment_id: str) -> Dict:
        """
        Process patient's SMS response
        
        Args:
            from_phone: Patient's phone number
            message_body: SMS response content
            appointment_id: Related appointment ID
            
        Returns:
            Dictionary with processed response details
        """
        message_upper = message_body.upper().strip()
        
        response = {
            'appointment_id': appointment_id,
            'from_phone': from_phone,
            'message': message_body,
            'timestamp': datetime.now().isoformat(),
            'action': None,
            'details': None
        }
        
        if 'YES' in message_upper or 'CONFIRM' in message_upper:
            response['action'] = 'confirmed'
            response['details'] = 'Appointment confirmed by patient'
            
        elif 'CANCEL' in message_upper:
            # Extract cancellation reason
            reason_start = message_upper.find('CANCEL') + 6
            reason = message_body[reason_start:].strip() if reason_start < len(message_body) else "No reason provided"
            response['action'] = 'cancelled'
            response['details'] = f"Cancellation reason: {reason}"
            
        elif 'FORMS' in message_upper:
            response['action'] = 'forms_completed'
            response['details'] = 'Patient confirmed form completion'
            
        elif 'HELP' in message_upper:
            response['action'] = 'help_requested'
            response['details'] = 'Patient requested assistance'
            
        else:
            response['action'] = 'unknown'
            response['details'] = 'Response not recognized'
        
        logger.info(f"Processed SMS response for appointment {appointment_id}: {response['action']}")
        return response
    
    def get_reminder_history(self, appointment_id: str) -> List[Dict]:
        """
        Get reminder history for an appointment
        
        Args:
            appointment_id: Appointment ID
            
        Returns:
            List of reminder records
        """
        return self.sent_reminders.get(appointment_id, [])
    
    def generate_reminder_report(self) -> Dict:
        """
        Generate summary report of all reminders
        
        Returns:
            Dictionary with reminder statistics
        """
        total_sent = sum(len(reminders) for reminders in self.sent_reminders.values())
        
        stage_counts = {
            'regular': 0,
            'form_check': 0,
            'confirmation_check': 0
        }
        
        for reminders in self.sent_reminders.values():
            for reminder in reminders:
                stage = reminder.get('stage', 'regular')
                if stage in stage_counts:
                    stage_counts[stage] += 1
        
        return {
            'total_appointments': len(self.sent_reminders),
            'total_reminders_sent': total_sent,
            'reminders_by_stage': stage_counts,
            'mock_mode': self.mock_mode,
            'generated_at': datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    # Initialize in mock mode for testing
    sms_service = SMSService(mock_mode=True)
    
    # Create a test reminder
    test_reminder = SMSReminder(
        patient_phone="+1234567890",
        patient_name="John Doe",
        appointment_date=datetime.now() + timedelta(days=2),
        appointment_time="2:30 PM",
        doctor_name="Smith",
        stage=ReminderStage.FIRST,
        appointment_id="APT_001"
    )
    
    # Send reminder
    success, sid = sms_service.send_reminder(test_reminder)
    print(f"Reminder sent: {success}, SID: {sid}")
    
    # Schedule reminders for an appointment
    scheduled = sms_service.schedule_reminders(
        appointment_date=datetime.now() + timedelta(days=3),
        appointment_id="APT_002",
        patient_phone="+1234567890",
        patient_name="Jane Doe",
        doctor_name="Johnson",
        appointment_time="10:00 AM"
    )
    print(f"Scheduled {len(scheduled)} reminders")
    
    # Process a response
    response = sms_service.process_sms_response(
        from_phone="+1234567890",
        message_body="YES",
        appointment_id="APT_001"
    )
    print(f"Processed response: {response}")