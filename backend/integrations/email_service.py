"""
Email Service for Medical Appointment System
Handles confirmation emails, form distribution, and reminder emails
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
from jinja2 import Template

__all__ = ['EmailService', 'SMSService', 'CalendlyService']

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service for sending appointment confirmations, intake forms, and reminders
    """
    
    def __init__(self, smtp_config: Optional[Dict] = None, use_mock: bool = True):
        """
        Initialize email service
        
        Args:
            smtp_config: SMTP configuration (server, port, username, password)
            use_mock: Use mock email sending for testing
        """
        self.use_mock = use_mock
        
        if not use_mock and smtp_config:
            self.smtp_server = smtp_config.get('server', os.getenv('SMTP_SERVER', 'smtp.sendgrid.net'))
            self.smtp_port = smtp_config.get('port', int(os.getenv('SMTP_PORT', '587')))
            self.smtp_username = smtp_config.get('username', os.getenv('SMTP_USERNAME'))
            self.smtp_password = smtp_config.get('password', os.getenv('SMTP_PASSWORD'))
            self.from_email = smtp_config.get('from_email', os.getenv('SMTP_FROM_EMAIL', self.smtp_username))
        else:
            # Mock configuration
            self.from_email = "appointments@medicalclinic.com"
        
        # Email log for mock mode
        self.email_log_file = Path("data/email_log.json")
        self.email_templates = self._load_email_templates()
        
        # Initialize email log
        if self.use_mock and not self.email_log_file.exists():
            self.email_log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.email_log_file, 'w') as f:
                json.dump([], f)
    
    def _load_email_templates(self) -> Dict[str, Template]:
        """Load email templates for different purposes"""
        templates = {
            'confirmation': Template("""
Subject: Appointment Confirmation - {{ doctor_name }} on {{ appointment_date }}

Dear {{ patient_name }},

Your appointment has been successfully scheduled!

APPOINTMENT DETAILS:
-------------------
Date: {{ appointment_date }}
Time: {{ appointment_time }}
Doctor: {{ doctor_name }}
Duration: {{ duration }}
Location: {{ location }}
Type: {{ appointment_type }}

IMPORTANT REMINDERS:
-------------------
• Please arrive 15 minutes early for check-in
• Bring your insurance card and photo ID
• Complete the intake forms sent separately
• If you need to cancel or reschedule, please call us at least 24 hours in advance

INSURANCE INFORMATION ON FILE:
-----------------------------
Carrier: {{ insurance_carrier }}
Member ID: {{ insurance_member_id }}
Group: {{ insurance_group }}

If you have any questions, please contact us at (555) 123-4567.

Thank you for choosing our clinic!

Best regards,
Medical Scheduling Team
            """),
            
            'intake_forms': Template("""
Subject: Patient Intake Forms - Please Complete Before Your Appointment

Dear {{ patient_name }},

Thank you for scheduling your appointment with {{ doctor_name }} on {{ appointment_date }}.

To ensure a smooth visit, please complete the attached intake forms before your appointment:

ATTACHED FORMS:
--------------
1. Patient Information Form
2. Medical History Questionnaire
3. Insurance Verification Form
4. Consent Forms

You can either:
• Complete the forms digitally and email them back
• Print, complete, and bring them to your appointment
• Arrive 20 minutes early to complete them at the clinic

APPOINTMENT REMINDER:
--------------------
Date: {{ appointment_date }}
Time: {{ appointment_time }}
Location: {{ location }}

If you have any questions about the forms, please don't hesitate to contact us.

Best regards,
Medical Scheduling Team
            """),
            
            'reminder_first': Template("""
Subject: Appointment Reminder - {{ days_until }} Days Until Your Visit

Dear {{ patient_name }},

This is a friendly reminder about your upcoming appointment:

Date: {{ appointment_date }}
Time: {{ appointment_time }}
Doctor: {{ doctor_name }}
Location: {{ location }}

Please remember to:
✓ Complete your intake forms (sent separately)
✓ Bring your insurance card and photo ID
✓ Arrive 15 minutes early

To confirm your appointment, please reply to this email or call us at (555) 123-4567.

Thank you!
Medical Scheduling Team
            """),
            
            'reminder_second': Template("""
Subject: ACTION REQUIRED - Appointment Tomorrow at {{ appointment_time }}

Dear {{ patient_name }},

Your appointment is TOMORROW!

APPOINTMENT DETAILS:
-------------------
Date: {{ appointment_date }}
Time: {{ appointment_time }}
Doctor: {{ doctor_name }}
Location: {{ location }}

ACTION REQUIRED:
---------------
□ Have you completed your intake forms? 
   If not, please complete them before arrival or arrive 20 minutes early.

□ Please confirm your attendance:
   - Reply 'YES' to confirm
   - Reply 'NO' to cancel (please provide reason)
   - Call us at (555) 123-4567

CHECKLIST FOR TOMORROW:
----------------------
• Insurance card
• Photo ID
• Completed forms
• List of current medications
• Any relevant medical records

See you tomorrow!
Medical Scheduling Team
            """),
            
            'reminder_third': Template("""
Subject: FINAL REMINDER - Your Appointment Today at {{ appointment_time }}

Dear {{ patient_name }},

This is your FINAL REMINDER for today's appointment:

⏰ Time: {{ appointment_time }} (in {{ hours_until }} hours)
📍 Location: {{ location }}
👨‍⚕️ Doctor: {{ doctor_name }}

IMPORTANT QUESTIONS:
-------------------
1. Have you completed your intake forms?
   □ Yes □ No (arrive 20 min early)

2. Are you still able to attend?
   □ Yes, I'll be there
   □ No, I need to cancel because: ___________

Please respond immediately if you need to cancel or reschedule.

Don't forget:
• Insurance card
• Photo ID
• Arrive 15 minutes early

We look forward to seeing you today!

Medical Scheduling Team
For urgent matters: (555) 123-4567
            """),
            
            'cancellation': Template("""
Subject: Appointment Cancellation Confirmation

Dear {{ patient_name }},

Your appointment scheduled for {{ appointment_date }} at {{ appointment_time }} with {{ doctor_name }} has been cancelled.

Cancellation Reason: {{ cancellation_reason }}

If you would like to reschedule, please contact us at (555) 123-4567 or reply to this email.

Thank you for letting us know.

Best regards,
Medical Scheduling Team
            """)
        }
        
        return templates
    
    def send_email(self, to_email: str, subject: str, body: str, attachments: Optional[List[Dict]] = None,
                   appointment_id: Optional[str] = None) -> bool:
        """
        Public method to send an email with optional attachments.
        Uses MIMEMultipart for attachment support and falls back to plain text when no attachments are provided.
        Returns True on success, False otherwise.
        """
        try:
            result = self._send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                email_type='generic',
                appointment_id=appointment_id,
                attachments=attachments or []
            )
            return bool(result and result.get('success'))
        except Exception as e:
            logger.error(f"send_email failed: {e}")
            return False

    def send_confirmation_email(self, appointment_data: Dict) -> Dict[str, Any]:
        """
        Send appointment confirmation email
        
        Args:
            appointment_data: Appointment details including patient and doctor info
        
        Returns:
            Send status and confirmation
        """
        patient_email = appointment_data.get('patient_data', {}).get('email')
        if not patient_email:
            return {
                'success': False,
                'message': 'No patient email provided'
            }
        
        # Parse appointment datetime
        apt_datetime = datetime.fromisoformat(appointment_data.get('datetime'))
        
        # Prepare template variables
        template_vars = {
            'patient_name': appointment_data.get('patient_data', {}).get('name'),
            'doctor_name': appointment_data.get('details', {}).get('doctor', 'Doctor'),
            'appointment_date': apt_datetime.strftime('%A, %B %d, %Y'),
            'appointment_time': apt_datetime.strftime('%I:%M %p'),
            'duration': appointment_data.get('details', {}).get('duration', '30 minutes'),
            'location': appointment_data.get('details', {}).get('location', 'Main Clinic'),
            'appointment_type': appointment_data.get('appointment_type', 'Regular Visit'),
            'insurance_carrier': appointment_data.get('patient_data', {}).get('insurance_carrier', 'N/A'),
            'insurance_member_id': appointment_data.get('patient_data', {}).get('insurance_member_id', 'N/A'),
            'insurance_group': appointment_data.get('patient_data', {}).get('insurance_group', 'N/A')
        }
        
        # Generate email content
        email_content = self.email_templates['confirmation'].render(**template_vars)
        
        # Extract subject and body
        lines = email_content.strip().split('\n')
        subject = lines[0].replace('Subject: ', '')
        body = '\n'.join(lines[2:])  # Skip subject line and blank line
        
        # Send email
        return self._send_email(
            to_email=patient_email,
            subject=subject,
            body=body,
            email_type='confirmation',
            appointment_id=appointment_data.get('appointment_id')
        )
    
    def send_intake_forms(self, appointment_data: Dict) -> Dict[str, Any]:
        """
        Send patient intake forms after appointment confirmation
        
        Args:
            appointment_data: Appointment details
        
        Returns:
            Send status
        """
        patient_email = appointment_data.get('patient_data', {}).get('email')
        if not patient_email:
            return {
                'success': False,
                'message': 'No patient email provided'
            }
        
        # Parse appointment datetime
        apt_datetime = datetime.fromisoformat(appointment_data.get('datetime'))
        
        # Prepare template variables
        template_vars = {
            'patient_name': appointment_data.get('patient_data', {}).get('name'),
            'doctor_name': appointment_data.get('details', {}).get('doctor', 'Doctor'),
            'appointment_date': apt_datetime.strftime('%A, %B %d, %Y'),
            'appointment_time': apt_datetime.strftime('%I:%M %p'),
            'location': appointment_data.get('details', {}).get('location', 'Main Clinic')
        }
        
        # Generate email content
        email_content = self.email_templates['intake_forms'].render(**template_vars)
        
        # Extract subject and body
        lines = email_content.strip().split('\n')
        subject = lines[0].replace('Subject: ', '')
        body = '\n'.join(lines[2:])
        
        # Prepare attachments (forms)
        attachments = self._get_intake_form_attachments()
        
        # Send email with attachments
        return self._send_email(
            to_email=patient_email,
            subject=subject,
            body=body,
            email_type='intake_forms',
            appointment_id=appointment_data.get('appointment_id'),
            attachments=attachments
        )
    
    def send_reminder_email(self, appointment_data: Dict, reminder_stage: int) -> Dict[str, Any]:
        """
        Send appointment reminder emails (3 stages)
        
        Args:
            appointment_data: Appointment details
            reminder_stage: 1, 2, or 3 (corresponding to different reminder templates)
        
        Returns:
            Send status
        """
        patient_email = appointment_data.get('patient_data', {}).get('email')
        if not patient_email:
            return {
                'success': False,
                'message': 'No patient email provided'
            }
        
        # Parse appointment datetime
        apt_datetime = datetime.fromisoformat(appointment_data.get('datetime'))
        now = datetime.now()
        time_until = apt_datetime - now
        
        # Select template based on stage
        template_map = {
            1: 'reminder_first',
            2: 'reminder_second',
            3: 'reminder_third'
        }
        
        template_key = template_map.get(reminder_stage, 'reminder_first')
        
        # Prepare template variables
        template_vars = {
            'patient_name': appointment_data.get('patient_data', {}).get('name'),
            'doctor_name': appointment_data.get('details', {}).get('doctor', 'Doctor'),
            'appointment_date': apt_datetime.strftime('%A, %B %d, %Y'),
            'appointment_time': apt_datetime.strftime('%I:%M %p'),
            'location': appointment_data.get('details', {}).get('location', 'Main Clinic'),
            'days_until': time_until.days,
            'hours_until': int(time_until.total_seconds() / 3600)
        }
        
        # Generate email content
        email_content = self.email_templates[template_key].render(**template_vars)
        
        # Extract subject and body
        lines = email_content.strip().split('\n')
        subject = lines[0].replace('Subject: ', '')
        body = '\n'.join(lines[2:])
        
        # Send email
        result = self._send_email(
            to_email=patient_email,
            subject=subject,
            body=body,
            email_type=f'reminder_stage_{reminder_stage}',
            appointment_id=appointment_data.get('appointment_id')
        )
        
        # Update reminder tracking
        if result['success']:
            self._update_reminder_tracking(appointment_data.get('appointment_id'), reminder_stage)
        
        return result
    
    def send_cancellation_email(self, appointment_data: Dict, reason: str) -> Dict[str, Any]:
        """
        Send appointment cancellation confirmation
        
        Args:
            appointment_data: Appointment details
            reason: Cancellation reason
        
        Returns:
            Send status
        """
        patient_email = appointment_data.get('patient_data', {}).get('email')
        if not patient_email:
            return {
                'success': False,
                'message': 'No patient email provided'
            }
        
        # Parse appointment datetime
        apt_datetime = datetime.fromisoformat(appointment_data.get('datetime'))
        
        # Prepare template variables
        template_vars = {
            'patient_name': appointment_data.get('patient_data', {}).get('name'),
            'doctor_name': appointment_data.get('details', {}).get('doctor', 'Doctor'),
            'appointment_date': apt_datetime.strftime('%A, %B %d, %Y'),
            'appointment_time': apt_datetime.strftime('%I:%M %p'),
            'cancellation_reason': reason
        }
        
        # Generate email content
        email_content = self.email_templates['cancellation'].render(**template_vars)
        
        # Extract subject and body
        lines = email_content.strip().split('\n')
        subject = lines[0].replace('Subject: ', '')
        body = '\n'.join(lines[2:])
        
        # Send email
        return self._send_email(
            to_email=patient_email,
            subject=subject,
            body=body,
            email_type='cancellation',
            appointment_id=appointment_data.get('appointment_id')
        )
    
    def _send_email(self, to_email: str, subject: str, body: str, 
                   email_type: str, appointment_id: Optional[str] = None,
                   attachments: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Core email sending function
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body
            email_type: Type of email for logging
            appointment_id: Related appointment ID
            attachments: List of attachment dictionaries
        
        Returns:
            Send status
        """
        if self.use_mock:
            return self._mock_send_email(to_email, subject, body, email_type, 
                                        appointment_id, attachments)
        else:
            return self._smtp_send_email(to_email, subject, body, attachments)
    
    def _mock_send_email(self, to_email: str, subject: str, body: str,
                        email_type: str, appointment_id: Optional[str],
                        attachments: Optional[List[Dict]]) -> Dict[str, Any]:
        """Mock email sending for testing"""
        # Load email log
        with open(self.email_log_file, 'r') as f:
            email_log = json.load(f)
        
        # Create email record
        email_record = {
            'email_id': f"EMAIL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(email_log)+1:04d}",
            'to': to_email,
            'from': self.from_email,
            'subject': subject,
            'body': body[:500] + '...' if len(body) > 500 else body,  # Truncate for log
            'type': email_type,
            'appointment_id': appointment_id,
            'attachments': [att['filename'] for att in (attachments or [])],
            'sent_at': datetime.now().isoformat(),
            'status': 'sent'
        }
        
        # Add to log
        email_log.append(email_record)
        
        # Save log
        with open(self.email_log_file, 'w') as f:
            json.dump(email_log, f, indent=2, default=str)
        
        logger.info(f"Mock email sent: {email_type} to {to_email}")
        
        return {
            'success': True,
            'message': f"Email sent successfully to {to_email}",
            'email_id': email_record['email_id'],
            'mock_mode': True
        }
    
    def _smtp_send_email(self, to_email: str, subject: str, body: str,
                        attachments: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    self._attach_file(msg, attachment)
            
            # Send email - handle different SMTP configurations
            if self.smtp_port == 465:  # SSL port (e.g., SendGrid SSL)
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            else:  # TLS port (e.g., 587)
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            
            return {
                'success': True,
                'message': f"Email sent successfully to {to_email}"
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {
                'success': False,
                'message': f"Failed to send email: {str(e)}"
            }
    
    def _attach_file(self, msg: MIMEMultipart, attachment: Dict):
        """Attach file to email message"""
        try:
            # Open file
            with open(attachment['path'], 'rb') as f:
                # Create attachment
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                
            # Encode
            encoders.encode_base64(part)
            
            # Add header
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment["filename"]}'
            )
            
            # Attach to message
            msg.attach(part)
            
        except Exception as e:
            logger.error(f"Failed to attach file {attachment.get('filename')}: {str(e)}")
    
    def _get_intake_form_attachments(self) -> List[Dict]:
        """Get intake form attachments"""
        forms_dir = Path("data/forms")
        attachments = []
        
        # Default form files
        form_files = [
            "patient_information_form.pdf",
            "medical_history_form.pdf",
            "insurance_verification_form.pdf",
            "consent_form.pdf"
        ]
        
        for form_file in form_files:
            form_path = forms_dir / form_file
            if form_path.exists():
                attachments.append({
                    'filename': form_file,
                    'path': str(form_path)
                })
            else:
                # Create a placeholder if form doesn't exist
                logger.warning(f"Form {form_file} not found, creating placeholder")
                # In production, you'd have actual PDF forms
        
        # If no forms exist, create a sample
        if not attachments and forms_dir.exists():
            sample_form = forms_dir / "intake_form.pdf"
            if sample_form.exists():
                attachments.append({
                    'filename': "intake_form.pdf",
                    'path': str(sample_form)
                })
        
        return attachments
    
    def _update_reminder_tracking(self, appointment_id: str, reminder_stage: int):
        """Update reminder tracking for an appointment"""
        if self.use_mock:
            # Update in appointments file
            appointments_file = Path("data/appointments.json")
            if appointments_file.exists():
                with open(appointments_file, 'r') as f:
                    appointments = json.load(f)
                
                for apt in appointments:
                    if apt.get('appointment_id') == appointment_id:
                        if 'reminders_sent' not in apt:
                            apt['reminders_sent'] = []
                        apt['reminders_sent'].append({
                            'stage': reminder_stage,
                            'sent_at': datetime.now().isoformat()
                        })
                        break
                
                with open(appointments_file, 'w') as f:
                    json.dump(appointments, f, indent=2, default=str)
    
    def get_email_history(self, appointment_id: Optional[str] = None) -> List[Dict]:
        """
        Get email history for an appointment or all emails
        
        Args:
            appointment_id: Optional appointment ID to filter by
        
        Returns:
            List of email records
        """
        if not self.email_log_file.exists():
            return []
        
        with open(self.email_log_file, 'r') as f:
            email_log = json.load(f)
        
        if appointment_id:
            return [email for email in email_log if email.get('appointment_id') == appointment_id]
        
        return email_log
    
    def verify_forms_completion(self, appointment_id: str) -> bool:
        """
        Check if patient has received and potentially completed forms
        
        Args:
            appointment_id: Appointment ID
        
        Returns:
            Boolean indicating if forms were sent
        """
        emails = self.get_email_history(appointment_id)
        return any(email.get('type') == 'intake_forms' for email in emails)