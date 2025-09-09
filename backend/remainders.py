"""
Reminder System for Medical Appointments
Implements 3-stage automated reminder workflow with confirmations
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio
from dataclasses import dataclass, asdict
import logging
import pandas as pd
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReminderType(Enum):
    """Types of reminders"""
    STANDARD = "standard"  # 1st reminder - just informational
    FORM_CHECK = "form_check"  # 2nd reminder - check if forms filled
    CONFIRMATION = "confirmation"  # 3rd reminder - confirm or cancel

class ReminderStatus(Enum):
    """Status of reminder sending"""
    PENDING = "pending"
    SENT = "sent"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AppointmentStatus(Enum):
    """Appointment confirmation status"""
    CONFIRMED = "confirmed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"

@dataclass
class Reminder:
    """Reminder data structure"""
    reminder_id: str
    appointment_id: str
    patient_name: str
    patient_email: str
    patient_phone: str
    appointment_datetime: datetime
    reminder_type: ReminderType
    scheduled_time: datetime
    status: ReminderStatus
    message_content: str
    response: Optional[str] = None
    sent_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['appointment_datetime'] = self.appointment_datetime.isoformat()
        data['scheduled_time'] = self.scheduled_time.isoformat()
        data['sent_time'] = self.sent_time.isoformat() if self.sent_time else None
        data['reminder_type'] = self.reminder_type.value
        data['status'] = self.status.value
        return data

@dataclass
class AppointmentReminder:
    """Complete appointment reminder tracking"""
    appointment_id: str
    patient_name: str
    patient_email: str
    patient_phone: str
    appointment_datetime: datetime
    doctor_name: str
    location: str
    appointment_status: AppointmentStatus
    forms_completed: bool = False
    cancellation_reason: Optional[str] = None
    reminders: List[Reminder] = None
    
    def __post_init__(self):
        if self.reminders is None:
            self.reminders = []

class ReminderSystem:
    """Manages the 3-stage reminder workflow"""
    
    def __init__(self, email_service=None, sms_service=None):
        """
        Initialize reminder system
        
        Args:
            email_service: Email service for sending emails
            sms_service: SMS service for sending text messages
        """
        self.email_service = email_service
        self.sms_service = sms_service
        self.appointments: Dict[str, AppointmentReminder] = {}
        self.reminder_queue: List[Reminder] = []
        self.reminder_log_path = Path("data/exports/reminder_log.json")
        self.load_reminder_log()
        
    def load_reminder_log(self):
        """Load existing reminder log from file"""
        if self.reminder_log_path.exists():
            try:
                with open(self.reminder_log_path, 'r') as f:
                    data = json.load(f)
                    # Reconstruct appointments from log
                    logger.info(f"Loaded {len(data)} appointment reminders from log")
            except Exception as e:
                logger.error(f"Error loading reminder log: {e}")
    
    def save_reminder_log(self):
        """Save reminder log to file"""
        try:
            # Ensure directory exists
            self.reminder_log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to serializable format
            log_data = []
            for appointment in self.appointments.values():
                appointment_dict = {
                    'appointment_id': appointment.appointment_id,
                    'patient_name': appointment.patient_name,
                    'patient_email': appointment.patient_email,
                    'patient_phone': appointment.patient_phone,
                    'appointment_datetime': appointment.appointment_datetime.isoformat(),
                    'doctor_name': appointment.doctor_name,
                    'location': appointment.location,
                    'appointment_status': appointment.appointment_status.value,
                    'forms_completed': appointment.forms_completed,
                    'cancellation_reason': appointment.cancellation_reason,
                    'reminders': [r.to_dict() for r in appointment.reminders]
                }
                log_data.append(appointment_dict)
            
            with open(self.reminder_log_path, 'w') as f:
                json.dump(log_data, f, indent=2)
            
            logger.info(f"Saved {len(log_data)} appointment reminders to log")
            
        except Exception as e:
            logger.error(f"Error saving reminder log: {e}")
    
    def schedule_appointment_reminders(self, appointment_data: Dict[str, Any]) -> AppointmentReminder:
        """
        Schedule the new 3-stage reminder workflow.
        R1: Immediate (confirmation + intake forms attachment)
        R2: Appointment - 1 day
        R3: Appointment - 2 hours
        """
        # Parse appointment data
        appointment_id = appointment_data.get('appointment_id', 
                                             datetime.now().strftime("%Y%m%d%H%M%S"))
        appointment_datetime = appointment_data['appointment_datetime']
        if isinstance(appointment_datetime, str):
            appointment_datetime = datetime.fromisoformat(appointment_datetime)
        
        # Create appointment reminder tracking
        appointment = AppointmentReminder(
            appointment_id=appointment_id,
            patient_name=appointment_data['patient_name'],
            patient_email=appointment_data['patient_email'],
            patient_phone=appointment_data['patient_phone'],
            appointment_datetime=appointment_datetime,
            doctor_name=appointment_data['doctor_name'],
            location=appointment_data.get('location', 'Main Clinic'),
            appointment_status=AppointmentStatus.PENDING
        )
        # Get the actual duration from appointment data
        duration_minutes = appointment_data.get('appointment_duration', 30)
        duration_text = f"{duration_minutes} minutes" if duration_minutes == 30 else f"{duration_minutes // 60} hour" if duration_minutes == 60 else f"{duration_minutes} minutes"
        
        # Build and send Reminder 1 immediately (confirmation + intake forms)
        r1 = Reminder(
            reminder_id=f"{appointment_id}_{ReminderType.STANDARD.value}",
            appointment_id=appointment_id,
            patient_name=appointment.patient_name,
            patient_email=appointment.patient_email,
            patient_phone=appointment.patient_phone,
            appointment_datetime=appointment_datetime,
            reminder_type=ReminderType.STANDARD,
            scheduled_time=datetime.now(),
            status=ReminderStatus.PENDING,
            message_content=(
                f"Dear {appointment.patient_name},\n\n"
                f"Your appointment is confirmed.\n\n"
                f"Patient: {appointment.patient_name}\n"
                f"Doctor: {appointment.doctor_name}\n"
                f"Location: {appointment.location}\n"
                f"Date: {appointment.appointment_datetime.strftime('%A, %B %d, %Y')}\n"
                f"Time: {appointment.appointment_datetime.strftime('%I:%M %p')}\n"
                f"Duration: {duration_text}\n\n"
                f"We've attached your intake forms. Please complete them before your visit."
            )
        )
        appointment.reminders.append(r1)

        # Attempt to send R1 now with intake_forms.pdf attachment
        try:
            if self.email_service and appointment.patient_email:
                subject = "Appointment Confirmation & Intake Forms"
                # Always use the absolute path provided by user request
                form_path = "C:/Users/saiha/OneDrive/Documents/RagaAI Assignment/data/forms/Intake_Form.pdf"
                attachments = [{'type': 'file', 'path': form_path, 'filename': 'Intake_Form.pdf'}]
                if hasattr(self.email_service, 'send_email'):
                    self.email_service.send_email(
                        to_email=appointment.patient_email,
                        subject=subject,
                        body=r1.message_content,
                        attachments=attachments,
                        appointment_id=appointment_id,
                    )
            if self.sms_service and appointment.patient_phone:
                sms_text = "Appt confirmed. Intake form attached in email."
                # Prefer send_sms if available, else fallback to send_reminder
                if hasattr(self.sms_service, 'send_sms'):
                    self.sms_service.send_sms(phone_number=appointment.patient_phone, message=sms_text)
                elif hasattr(self.sms_service, 'send_reminder'):
                    try:
                        # Construct a lightweight reminder object compatible with SMSService
                        from backend.integrations.sms_service import SMSReminder, ReminderStage  # type: ignore
                        sms_rem = SMSReminder(
                            patient_phone=appointment.patient_phone,
                            patient_name=appointment.patient_name,
                            appointment_date=appointment.appointment_datetime,
                            appointment_time=appointment.appointment_datetime.strftime('%I:%M %p'),
                            doctor_name=appointment.doctor_name,
                            stage=ReminderStage.FIRST,
                            appointment_id=appointment_id
                        )
                        self.sms_service.send_reminder(sms_rem)
                    except Exception:
                        pass
            # Mark R1 sent
            r1.status = ReminderStatus.SENT
            r1.sent_time = datetime.now()
            # Mark forms sent
            appointment.forms_completed = False
        except Exception as e:
            logger.error(f"Failed sending immediate Reminder 1: {e}")

        # Schedule Reminder 2 (1 day before)
        r2_time = appointment_datetime - timedelta(days=1)
        r2 = Reminder(
            reminder_id=f"{appointment_id}_{ReminderType.FORM_CHECK.value}",
            appointment_id=appointment_id,
            patient_name=appointment.patient_name,
            patient_email=appointment.patient_email,
            patient_phone=appointment.patient_phone,
            appointment_datetime=appointment_datetime,
            reminder_type=ReminderType.FORM_CHECK,
            scheduled_time=r2_time,
            status=ReminderStatus.PENDING,
            message_content=(
                "Have you completed your intake forms? Please do so before your visit. "
                "Also, please confirm if you are attending. If you cannot attend, reply with 'Appointment - Cancel' to free up this slot."
            )
        )
        appointment.reminders.append(r2)
        self.reminder_queue.append(r2)

        # Schedule Reminder 3 (2 hours before)
        r3_time = appointment_datetime - timedelta(hours=2)
        r3 = Reminder(
            reminder_id=f"{appointment_id}_{ReminderType.CONFIRMATION.value}",
            appointment_id=appointment_id,
            patient_name=appointment.patient_name,
            patient_email=appointment.patient_email,
            patient_phone=appointment.patient_phone,
            appointment_datetime=appointment_datetime,
            reminder_type=ReminderType.CONFIRMATION,
            scheduled_time=r3_time,
            status=ReminderStatus.PENDING,
            message_content=(
                "This is your final reminder. Please confirm your attendance. "
                "If you are not attending, reply 'Appointment - Cancel' immediately."
            )
        )
        appointment.reminders.append(r3)
        self.reminder_queue.append(r3)

        # Store appointment
        self.appointments[appointment_id] = appointment
        self.save_reminder_log()
        
        logger.info(f"Scheduled 3 reminders (R1 sent immediately) for appointment {appointment_id}")
        
        return appointment
    
    def _get_standard_reminder_template(self) -> str:
        """Get template for standard reminder (1 week before)"""
        return """
Dear {patient_name},

This is a reminder of your upcoming appointment:

📅 Date: {appointment_date}
⏰ Time: {appointment_time}
👨‍⚕️ Doctor: {doctor_name}
📍 Location: {location}

Please ensure you arrive 15 minutes early for check-in.

If you need to reschedule or cancel, please call us at (555) 123-4567.

Thank you,
[Clinic Name] Medical Center
"""
    
    def _get_form_check_template(self) -> str:
        """Get template for form check reminder (1 day before)"""
        return """
Dear {patient_name},

Your appointment is tomorrow!

📅 Date: {appointment_date}
⏰ Time: {appointment_time}
👨‍⚕️ Doctor: {doctor_name}
📍 Location: {location}

⚠️ IMPORTANT: Have you completed your intake forms?

If not, please complete them online at [clinic-portal-link] or arrive 30 minutes early to fill them out.

Reply with:
- YES if forms are completed
- NO if you need the forms resent
- HELP if you need assistance

See you tomorrow!
[Clinic Name] Medical Center
"""
    
    def _get_confirmation_template(self) -> str:
        """Get template for confirmation reminder (2 hours before)"""
        return """
Dear {patient_name},

Your appointment is in 2 HOURS!

📅 Today at {appointment_time}
👨‍⚕️ Doctor: {doctor_name}
📍 Location: {location}

Please confirm your appointment:

Reply with:
- CONFIRM to confirm you'll attend
- CANCEL to cancel (please provide reason)
- RESCHEDULE if you need to change the time

⏰ Remember to arrive 15 minutes early!

[Clinic Name] Medical Center
"""
    
    def _format_message(self, template: str, appointment: AppointmentReminder) -> str:
        """Format message template with appointment details"""
        return template.format(
            patient_name=appointment.patient_name,
            appointment_date=appointment.appointment_datetime.strftime("%A, %B %d, %Y"),
            appointment_time=appointment.appointment_datetime.strftime("%I:%M %p"),
            doctor_name=appointment.doctor_name,
            location=appointment.location
        )
    
    async def send_reminder(self, reminder: Reminder) -> bool:
        """
        Send a single reminder via email and SMS
        
        Args:
            reminder: Reminder to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        success = True
        
        try:
            # Send email
            if self.email_service and reminder.patient_email:
                email_subject = self._get_email_subject(reminder.reminder_type)
                email_sent = await self.email_service.send_email(
                    to_email=reminder.patient_email,
                    subject=email_subject,
                    body=reminder.message_content
                )
                if not email_sent:
                    logger.error(f"Failed to send email for reminder {reminder.reminder_id}")
                    success = False
            
            # Send SMS
            if self.sms_service and reminder.patient_phone:
                # Shorten message for SMS
                sms_content = self._shorten_for_sms(reminder.message_content)
                sms_sent = await self.sms_service.send_sms(
                    phone_number=reminder.patient_phone,
                    message=sms_content
                )
                if not sms_sent:
                    logger.error(f"Failed to send SMS for reminder {reminder.reminder_id}")
                    success = False
            
            # Update reminder status
            if success:
                reminder.status = ReminderStatus.SENT
                reminder.sent_time = datetime.now()
                logger.info(f"Successfully sent reminder {reminder.reminder_id}")
            else:
                reminder.status = ReminderStatus.FAILED
                logger.error(f"Failed to send reminder {reminder.reminder_id}")
            
            self.save_reminder_log()
            return success
            
        except Exception as e:
            logger.error(f"Error sending reminder {reminder.reminder_id}: {e}")
            reminder.status = ReminderStatus.FAILED
            self.save_reminder_log()
            return False
    
    def _get_email_subject(self, reminder_type: ReminderType) -> str:
        """Get email subject based on reminder type"""
        subjects = {
            ReminderType.STANDARD: "Appointment Confirmation & Intake Forms",
            ReminderType.FORM_CHECK: "Reminder: Your appointment is tomorrow",
            ReminderType.CONFIRMATION: "Final Confirmation: Your appointment today",
        }
        return subjects.get(reminder_type, "Appointment Reminder")
    
    def _shorten_for_sms(self, message: str, max_length: int = 160) -> str:
        """Shorten message for SMS"""
        # Extract key information
        lines = message.split('\n')
        key_lines = [line for line in lines if any(
            marker in line for marker in ['Date:', 'Time:', 'Doctor:', 'Reply with:']
        )]
        
        short_message = '\n'.join(key_lines[:4])
        
        if len(short_message) > max_length:
            short_message = short_message[:max_length-3] + "..."
        
        return short_message

    def reopen_slot(self, appointment_id: str, doctor: str, date: str, time: str, channel: str = "reminder-auto") -> bool:
        """
        Reopen a booked slot in data/appointments.xlsx by marking it available
        and clearing patient_name and patient_email. Also set appointment_status=cancelled.
        """
        try:
            schedules_path = Path("data/appointments.xlsx")
            columns = ['doctor', 'date', 'time', 'location', 'available', 'patient_name', 'patient_email', 'patient_phone', 'appointment_status']
            if schedules_path.exists():
                try:
                    df = pd.read_excel(schedules_path)
                except Exception:
                    df = pd.DataFrame(columns=columns)
            else:
                df = pd.DataFrame(columns=columns)

            match = (df['doctor'] == doctor) & (df['date'] == date) & (df['time'] == time)
            
            # Get patient details before clearing them for logging
            patient_name = ""
            patient_email = ""
            patient_phone = ""
            
            if not df.empty and match.any():
                matched_row = df[match].iloc[0]
                patient_name = str(matched_row.get('patient_name', ''))
                patient_email = str(matched_row.get('patient_email', ''))
                patient_phone = str(matched_row.get('patient_phone', ''))
            
            if df.empty or not match.any():
                # create a row explicitly marked available
                new_row = {
                    'doctor': doctor,
                    'date': date,
                    'time': time,
                    'location': 'Main Clinic',
                    'available': True,
                    'patient_name': '',
                    'patient_email': '',
                    'patient_phone': '',
                    'appointment_status': 'cancelled',
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            else:
                # Ensure status column exists
                if 'appointment_status' not in df.columns:
                    df['appointment_status'] = ''
                if 'patient_phone' not in df.columns:
                    df['patient_phone'] = ''
                df.loc[match, ['available', 'patient_name', 'patient_email', 'patient_phone', 'appointment_status']] = [True, '', '', '', 'cancelled']

            df.to_excel(schedules_path, index=False)
            logger.info(f"Reopened slot for {doctor} on {date} at {time} due to cancellation/no-show. (Appointment {appointment_id})")
            
            # Log the cancellation
            try:
                try:
                    from backend.cancellations import log_cancellation
                except ModuleNotFoundError:
                    from cancellations import log_cancellation
                log_cancellation(
                    appointment_id=appointment_id,
                    patient_name=patient_name,
                    patient_email=patient_email,
                    patient_phone=patient_phone,
                    doctor=doctor,
                    date=date,
                    time=time,
                    channel=channel
                )
            except Exception as e:
                logger.error(f"Failed to log cancellation: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to reopen slot for appointment {appointment_id}: {e}")
            return False

        except Exception as e:
            logger.error(f"Failed to process cancellation for appointment {appointment_id}: {e}")
            return False
    
    async def process_reminder_queue(self):
        """Process pending reminders in the queue"""
        current_time = datetime.now()
        
        for reminder in self.reminder_queue:
            if (reminder.status == ReminderStatus.PENDING and 
                reminder.scheduled_time <= current_time):
                
                logger.info(f"Processing reminder {reminder.reminder_id}")
                await self.send_reminder(reminder)
        
        # Remove sent/failed reminders from queue
        self.reminder_queue = [
            r for r in self.reminder_queue 
            if r.status == ReminderStatus.PENDING
        ]
    
    def process_patient_response(self, appointment_id: str, 
                                reminder_type: ReminderType,
                                response: str) -> Tuple[bool, str]:
        """
        Process patient response to reminders
        
        Args:
            appointment_id: ID of the appointment
            reminder_type: Type of reminder responded to
            response: Patient's response
            
        Returns:
            Tuple of (success, message)
        """
        if appointment_id not in self.appointments:
            return False, "Appointment not found"
        
        appointment = self.appointments[appointment_id]
        response_lower = response.lower().strip()
        
        # Find the specific reminder
        reminder = next(
            (r for r in appointment.reminders 
             if r.reminder_type == reminder_type),
            None
        )
        
        if not reminder:
            return False, "Reminder not found"
        
        reminder.response = response
        
        # Process based on reminder type
        if reminder_type == ReminderType.FORM_CHECK:
            if 'yes' in response_lower:
                appointment.forms_completed = True
                message = "Thank you! Forms marked as completed."
            elif 'no' in response_lower:
                # Trigger form resend
                message = "Forms will be resent to your email."
            else:
                message = "Response not understood. Please reply YES or NO."
        
        elif reminder_type == ReminderType.CONFIRMATION:
            if 'confirm' in response_lower:
                appointment.appointment_status = AppointmentStatus.CONFIRMED
                reminder.status = ReminderStatus.CONFIRMED
                message = "Appointment confirmed! See you soon."
            elif 'appointment - cancel' in response_lower or 'cancel' in response_lower:
                appointment.appointment_status = AppointmentStatus.CANCELLED
                # Extract cancellation reason if provided
                appointment.cancellation_reason = response
                message = "Appointment cancelled. Thank you for letting us know."
                # Reopen the slot in the schedule if possible
                try:
                    appt_dt = appointment.appointment_datetime
                    self.reopen_slot(
                        appointment_id=appointment.appointment_id,
                        doctor=appointment.doctor_name,
                        date=appt_dt.strftime('%Y-%m-%d'),
                        time=appt_dt.strftime('%H:%M'),
                    )
                except Exception:
                    pass
            elif 'reschedule' in response_lower:
                appointment.appointment_status = AppointmentStatus.RESCHEDULED
                message = "Please call (555) 123-4567 to reschedule your appointment."
            else:
                message = "Please reply CONFIRM, CANCEL, or RESCHEDULE."
        
        else:  # Standard reminder
            message = "Thank you for your response."
        
        self.save_reminder_log()
        return True, message
    
    def get_appointment_status(self, appointment_id: str) -> Optional[AppointmentStatus]:
        """Get current status of an appointment"""
        if appointment_id in self.appointments:
            return self.appointments[appointment_id].appointment_status
        return None
    
    def get_pending_reminders(self, time_window: timedelta = timedelta(hours=1)) -> List[Reminder]:
        """
        Get reminders that need to be sent within time window
        
        Args:
            time_window: Time window to check for pending reminders
            
        Returns:
            List of pending reminders
        """
        current_time = datetime.now()
        window_end = current_time + time_window
        
        pending = []
        for reminder in self.reminder_queue:
            if (reminder.status == ReminderStatus.PENDING and
                reminder.scheduled_time >= current_time and
                reminder.scheduled_time <= window_end):
                pending.append(reminder)
        
        return pending
    
    def cancel_appointment_reminders(self, appointment_id: str, reason: str = None) -> bool:
        """
        Cancel all reminders for an appointment
        
        Args:
            appointment_id: ID of appointment to cancel
            reason: Cancellation reason
            
        Returns:
            True if cancelled successfully
        """
        if appointment_id not in self.appointments:
            return False
        
        appointment = self.appointments[appointment_id]
        appointment.appointment_status = AppointmentStatus.CANCELLED
        appointment.cancellation_reason = reason
        
        # Cancel all pending reminders
        for reminder in appointment.reminders:
            if reminder.status == ReminderStatus.PENDING:
                reminder.status = ReminderStatus.CANCELLED
        
        # Remove from queue
        self.reminder_queue = [
            r for r in self.reminder_queue
            if r.appointment_id != appointment_id
        ]
        
        self.save_reminder_log()
        logger.info(f"Cancelled reminders for appointment {appointment_id}")
        
        return True
    
    def generate_reminder_report(self) -> pd.DataFrame:
        """Generate report of all reminders for admin review"""
        report_data = []
        
        for appointment in self.appointments.values():
            for reminder in appointment.reminders:
                report_data.append({
                    'Appointment ID': appointment.appointment_id,
                    'Patient Name': appointment.patient_name,
                    'Appointment Date': appointment.appointment_datetime.strftime("%Y-%m-%d %H:%M"),
                    'Doctor': appointment.doctor_name,
                    'Reminder Type': reminder.reminder_type.value,
                    'Scheduled Send': reminder.scheduled_time.strftime("%Y-%m-%d %H:%M"),
                    'Status': reminder.status.value,
                    'Sent Time': reminder.sent_time.strftime("%Y-%m-%d %H:%M") if reminder.sent_time else 'N/A',
                    'Patient Response': reminder.response or 'None',
                    'Forms Completed': appointment.forms_completed,
                    'Appointment Status': appointment.appointment_status.value,
                    'Cancellation Reason': appointment.cancellation_reason or 'N/A'
                })
        
        df = pd.DataFrame(report_data)
        
        # Save to Excel
        export_path = Path("data/exports/reminder_report.xlsx")
        export_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(export_path, index=False, sheet_name='Reminder Report')
        
        logger.info(f"Generated reminder report with {len(report_data)} entries")
        
        return df
    
    def get_reminder_statistics(self) -> Dict[str, Any]:
        """Get statistics about reminder system performance"""
        total_appointments = len(self.appointments)
        total_reminders = sum(len(a.reminders) for a in self.appointments.values())
        
        # Count by status
        status_counts = {status: 0 for status in ReminderStatus}
        appointment_status_counts = {status: 0 for status in AppointmentStatus}
        
        for appointment in self.appointments.values():
            appointment_status_counts[appointment.appointment_status] += 1
            for reminder in appointment.reminders:
                status_counts[reminder.status] += 1
        
        # Calculate response rates
        form_check_reminders = [
            r for a in self.appointments.values()
            for r in a.reminders
            if r.reminder_type == ReminderType.FORM_CHECK
        ]
        form_response_rate = (
            sum(1 for r in form_check_reminders if r.response) / 
            len(form_check_reminders) * 100
            if form_check_reminders else 0
        )
        
        confirmation_reminders = [
            r for a in self.appointments.values()
            for r in a.reminders
            if r.reminder_type == ReminderType.CONFIRMATION
        ]
        confirmation_response_rate = (
            sum(1 for r in confirmation_reminders if r.response) /
            len(confirmation_reminders) * 100
            if confirmation_reminders else 0
        )
        
        return {
            'total_appointments': total_appointments,
            'total_reminders': total_reminders,
            'reminder_status': {s.value: c for s, c in status_counts.items()},
            'appointment_status': {s.value: c for s, c in appointment_status_counts.items()},
            'form_response_rate': f"{form_response_rate:.1f}%",
            'confirmation_response_rate': f"{confirmation_response_rate:.1f}%",
            'no_show_rate': f"{(appointment_status_counts[AppointmentStatus.NO_SHOW] / total_appointments * 100):.1f}%" if total_appointments > 0 else "0%",
            'cancellation_rate': f"{(appointment_status_counts[AppointmentStatus.CANCELLED] / total_appointments * 100):.1f}%" if total_appointments > 0 else "0%"
        }
    
    def mark_no_shows(self):
        """Mark appointments as no-show if past appointment time without confirmation"""
        current_time = datetime.now()
        
        for appointment in self.appointments.values():
            if (appointment.appointment_datetime < current_time and
                appointment.appointment_status == AppointmentStatus.PENDING):
                
                appointment.appointment_status = AppointmentStatus.NO_SHOW
                logger.info(f"Marked appointment {appointment.appointment_id} as no-show")
                # Reopen slot
                try:
                    appt_dt = appointment.appointment_datetime
                    self.reopen_slot(
                        appointment_id=appointment.appointment_id,
                        doctor=appointment.doctor_name,
                        date=appt_dt.strftime('%Y-%m-%d'),
                        time=appt_dt.strftime('%H:%M'),
                    )
                except Exception:
                    pass
        
        self.save_reminder_log()


class ReminderScheduler:
    """Async scheduler for running reminder system"""
    
    def __init__(self, reminder_system: ReminderSystem):
        self.reminder_system = reminder_system
        self.running = False
        
    async def start(self):
        """Start the reminder scheduler"""
        self.running = True
        logger.info("Reminder scheduler started")
        try:
            while self.running:
                try:
                    # Process reminder queue
                    await self.reminder_system.process_reminder_queue()
                    
                    # Mark no-shows
                    self.reminder_system.mark_no_shows()
                    
                    # Sleep in short intervals to support fast shutdown
                    total_sleep_seconds = 300
                    interval_seconds = 1
                    for _ in range(0, total_sleep_seconds, interval_seconds):
                        if not self.running:
                            break
                        await asyncio.sleep(interval_seconds)
                    
                except Exception as e:
                    logger.error(f"Error in reminder scheduler: {e}")
                    # Short backoff and continue
                    for _ in range(60):
                        if not self.running:
                            break
                        await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Graceful shutdown
            logger.info("Reminder scheduler task cancelled")
            raise
    
    def stop(self):
        """Stop the reminder scheduler"""
        self.running = False
        logger.info("Reminder scheduler stopped")


# Utility functions for testing and simulation
def create_test_appointment(days_ahead: int = 7) -> Dict[str, Any]:
    """Create a test appointment for simulation"""
    appointment_time = datetime.now() + timedelta(days=days_ahead)
    
    return {
        'appointment_id': datetime.now().strftime("%Y%m%d%H%M%S"),
        'patient_name': 'John Doe',
        'patient_email': 'john.doe@example.com',
        'patient_phone': '+1234567890',
        'appointment_datetime': appointment_time,
        'doctor_name': 'Dr. Smith',
        'location': 'Main Clinic - Room 101'
    }


async def simulate_reminder_workflow():
    """Simulate the complete reminder workflow"""
    # Initialize services (mock for testing)
    # Support both `python -m backend.remainders` and `python backend/remainders.py`
    try:
        from backend.integrations.email_service import EmailService  # type: ignore
        from backend.integrations.sms_service import SMSService  # type: ignore
    except ModuleNotFoundError:
        from integrations.email_service import EmailService  # type: ignore
        from integrations.sms_service import SMSService  # type: ignore
    
    email_service = EmailService()
    sms_service = SMSService()
    
    # Create reminder system
    reminder_system = ReminderSystem(email_service, sms_service)
    
    # Schedule test appointment
    test_appointment = create_test_appointment(days_ahead=8)
    appointment = reminder_system.schedule_appointment_reminders(test_appointment)
    
    print(f"Scheduled reminders for appointment {appointment.appointment_id}")
    
    # Create scheduler
    scheduler = ReminderScheduler(reminder_system)
    
    # Run scheduler for simulation
    scheduler_task = asyncio.create_task(scheduler.start())
    
    # Simulate for a short period
    await asyncio.sleep(10)
    
    # Stop scheduler and wait for graceful exit
    scheduler.stop()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    
    # Generate report
    stats = reminder_system.get_reminder_statistics()
    print("\nReminder System Statistics:")
    print(json.dumps(stats, indent=2))
    
    # Generate Excel report
    report_df = reminder_system.generate_reminder_report()
    print(f"\nGenerated report with {len(report_df)} entries")


if __name__ == "__main__":
    # Run simulation
    asyncio.run(simulate_reminder_workflow())