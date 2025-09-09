#!/usr/bin/env python3
"""
Interactive Medical Scheduling Agent
Step-by-step conversation following the technical requirements
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.patient_lookup import PatientDatabase
from backend.integrations.calendly_service import CalendlyService
from backend.integrations.email_service import EmailService
from backend.integrations.sms_service import SMSService, SMSReminder, ReminderStage
from backend.remainders import ReminderSystem
from backend.insurance import InsuranceValidator
from backend.schedular import Scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from backend.email_cancellation import check_email_cancellations
import atexit
from langchain_groq import ChatGroq

class InteractiveMedicalAgent:
    def __init__(self, groq_api_key: str):
        """Initialize the interactive medical scheduling agent"""
        self.llm = ChatGroq(
            groq_api_key=groq_api_key,
            model_name="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=1024,
        )
        
        # Initialize all services with real configurations
        self.patient_db = PatientDatabase()
        self.calendly = CalendlyService(use_mock=True)
        
        # Email service configuration (using first Twilio account for emails)
        smtp_config = {
            'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('SMTP_USERNAME'),
            'password': os.getenv('SMTP_PASSWORD'),
            'from_email': os.getenv('SMTP_FROM_EMAIL', os.getenv('SMTP_USERNAME')),
            # Twilio email configuration
            'twilio_account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
            'twilio_auth_token': os.getenv('TWILIO_AUTH_TOKEN')
        }
        
        # Use real email service if credentials are available, otherwise mock
        use_real_email = bool(smtp_config['username'] and smtp_config['password'])
        self.email_service = EmailService(smtp_config=smtp_config, use_mock=not use_real_email)
        
        # SMS service configuration (using second Twilio account for SMS)
        twilio_account_sid_sms = os.getenv('TWILIO_ACCOUNT_SID1')
        twilio_auth_token_sms = os.getenv('TWILIO_AUTH_TOKEN1')
        twilio_phone_number_sms = os.getenv('TWILIO_PHONE_NUMBER1')
        
        # Use real SMS service if credentials are available, otherwise mock
        use_real_sms = bool(twilio_account_sid_sms and twilio_auth_token_sms and twilio_phone_number_sms)
        self.sms_service = SMSService(
            account_sid=twilio_account_sid_sms,
            auth_token=twilio_auth_token_sms,
            from_number=twilio_phone_number_sms,
            mock_mode=not use_real_sms
        )
        
        self.reminder_system = ReminderSystem(self.email_service, self.sms_service)
        self.insurance_validator = InsuranceValidator()
        self.scheduler = Scheduler()
        
        # Current appointment data
        self.appointment_data = {}
        
        # Print service status
        print(f"📧 Email Service: {'Real SMTP' if use_real_email else 'Mock Mode'}")
        print(f"📱 SMS Service: {'Real Twilio' if use_real_sms else 'Mock Mode'}")
        print()
        # Start background scheduler for email cancellations
        self._bg_scheduler = BackgroundScheduler()
        self._bg_scheduler.add_job(
            func=check_email_cancellations,
            trigger="interval",
            minutes=1,
            id="email_cancellation_checker",
            replace_existing=True,
        )
        self._bg_scheduler.start()
        print("📧 Email cancellation checker is running every 5 minutes...")
        atexit.register(lambda: self._bg_scheduler.shutdown())
        
    def validate_dob(self, dob_str: str) -> bool:
        """Validate DOB format MM/DD/YYYY"""
        import re
        return bool(re.match(r"^(0[1-9]|1[0-2])/(0[1-9]|[12][0-9]|3[01])/[0-9]{4}$", dob_str or ""))
    
    def validate_insurance_id(self, member_id: str) -> bool:
        """Validate insurance member ID"""
        import re
        return bool(re.match(r"^[A-Za-z0-9]{6,12}$", member_id or ""))
    
    def normalize_insurance(self, carrier: str) -> str:
        """Normalize insurance carrier name"""
        if not carrier:
            return "None"
        normalized = carrier.strip().lower()
        mapping = {
            "icici lombard": "ICICI Lombard",
            "hdfc ergo": "HDFC Ergo", 
            "star health": "Star Health",
            "religare": "Religare",
            "new india assurance": "New India Assurance",
            "none": "None",
            "self-pay": "None",
            "self pay": "None",
        }
        for key, value in mapping.items():
            if key in normalized:
                return value
        return carrier
    
    def get_llm_response(self, prompt: str) -> str:
        """Get response from LLM"""
        try:
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            return f"I apologize, but I'm having trouble processing that. Please try again. ({str(e)})"
    
    def step1_greeting_and_collect_info(self):
        """Step 1: Greeting and collect basic information"""
        print("🏥 Welcome to our Medical Scheduling System!")
        print("=" * 50)
        
        # Get patient name
        while not self.appointment_data.get('patient_name'):
            name = input("👤 Please enter your full name: ").strip()
            if name:
                self.appointment_data['patient_name'] = name
            else:
                print("❌ Please enter a valid name.")
        
        # Get DOB
        while not self.appointment_data.get('patient_dob'):
            dob = input("📅 Please enter your date of birth (MM/DD/YYYY): ").strip()
            if self.validate_dob(dob):
                self.appointment_data['patient_dob'] = dob
            else:
                print("❌ Please enter DOB in MM/DD/YYYY format (e.g., 03/15/1995).")
        
        # Get doctor preference
        while not self.appointment_data.get('doctor_preference'):
            print("\n👨‍⚕️ Please choose your preferred doctor:")
            print("1) Dr. Sharma - General Medicine")
            print("2) Dr. Iyer - Cardiology") 
            print("3) Dr. Mehta - Orthopedics")
            print("4) Dr. Kapoor - Dermatology")
            print("5) Dr. Reddy - Pediatrics")
            
            choice = input("Enter your choice (1-5): ").strip()
            doctors = ["Dr. Sharma", "Dr. Iyer", "Dr. Mehta", "Dr. Kapoor", "Dr. Reddy"]
            if choice.isdigit() and 1 <= int(choice) <= 5:
                self.appointment_data['doctor_preference'] = doctors[int(choice)-1]
            else:
                print("❌ Please enter a valid choice (1-5).")
        
        # Get location preference
        while not self.appointment_data.get('location_preference'):
            location = input("🏥 Please enter your preferred clinic location: ").strip()
            if location:
                self.appointment_data['location_preference'] = location
            else:
                print("❌ Please enter a valid location.")
        
        # Get phone number
        while not self.appointment_data.get('patient_phone'):
            phone = input("📱 Please enter your phone number: ").strip()
            if phone:
                self.appointment_data['patient_phone'] = phone
            else:
                print("❌ Please enter a valid phone number.")
        
        # Get email
        while not self.appointment_data.get('patient_email'):
            email = input("📧 Please enter your email address: ").strip()
            if email and "@" in email:
                self.appointment_data['patient_email'] = email
            else:
                print("❌ Please enter a valid email address.")
    
    def step2_patient_lookup(self):
        """Step 2: Patient lookup to determine new vs returning"""
        print("\n🔍 Looking up your patient record...")
        
        patient = self.patient_db.search_patient(
            self.appointment_data['patient_name'], 
            self.appointment_data['patient_dob']
        )
        
        if patient:
            self.appointment_data['patient_type'] = 'returning'
            self.appointment_data['appointment_duration'] = 30
            print(f"✅ Welcome back, {self.appointment_data['patient_name']}!")
            print("📋 You are a returning patient. Your appointment will be 30 minutes.")
            
            # Use existing insurance data for returning patients
            existing_insurance = patient.get('Insurance', 'None')
            # Handle NaN values from pandas
            if existing_insurance and str(existing_insurance).lower() not in ['none', 'nan', '']:
                self.appointment_data['insurance_carrier'] = str(existing_insurance)
                print(f"🏥 Using your existing insurance: {existing_insurance}")
            else:
                print("🏥 No insurance on file. We'll collect this information.")
        else:
            self.appointment_data['patient_type'] = 'new'
            self.appointment_data['appointment_duration'] = 60
            print(f"👋 Welcome, {self.appointment_data['patient_name']}!")
            print("📋 You are a new patient. Your first appointment will be 60 minutes.")
            print("🏥 We'll need to collect your insurance information.")
            
            # Add new patient to database
            self.patient_db.add_patient({
                "name": self.appointment_data['patient_name'],
                "dob": self.appointment_data['patient_dob'],
                "email": self.appointment_data['patient_email'],
                "phone": self.appointment_data['patient_phone'],
                "doctor": self.appointment_data['doctor_preference']
            })
    
    def step3_smart_scheduling(self):
        """Step 3: Smart scheduling - show available slots"""
        print(f"\n📅 Finding available slots with {self.appointment_data['doctor_preference']}...")
        
        # Map doctor name to ID
        doctor_mapping = {
            "Dr. Sharma": "dr_sharma",
            "Dr. Iyer": "dr_iyer", 
            "Dr. Mehta": "dr_mehta",
            "Dr. Kapoor": "dr_kapoor",
            "Dr. Reddy": "dr_reddy"
        }
        doctor_id = doctor_mapping[self.appointment_data['doctor_preference']]
        
        # Get available slots
        slots = self.calendly.get_available_slots(
            doctor_id=doctor_id,
            date_from=datetime.now(),
            date_to=datetime.now() + timedelta(days=14),
            duration_minutes=self.appointment_data['appointment_duration']
        )
        
        if not slots:
            print("❌ Sorry, no available slots found. Please try again later.")
            return False
        
        print(f"\n📋 Available slots for {self.appointment_data['appointment_duration']}-minute appointment:")
        for i, slot in enumerate(slots[:10], 1):  # Show first 10 slots
            slot_time = datetime.fromisoformat(slot['datetime'])
            print(f"{i}. {slot_time.strftime('%A, %B %d, %Y at %I:%M %p')}")
        
        # Get user selection
        while True:
            try:
                choice = int(input(f"\nPlease select a slot (1-{min(len(slots), 10)}): "))
                if 1 <= choice <= min(len(slots), 10):
                    selected_slot = slots[choice-1]
                    self.appointment_data['appointment_datetime'] = datetime.fromisoformat(selected_slot['datetime'])
                    self.appointment_data['selected_slot'] = selected_slot
                    print(f"✅ Selected: {self.appointment_data['appointment_datetime'].strftime('%A, %B %d, %Y at %I:%M %p')}")
                    return True
                else:
                    print(f"❌ Please enter a number between 1 and {min(len(slots), 10)}")
            except ValueError:
                print("❌ Please enter a valid number.")
    
    def step4_insurance_collection(self):
        """Step 4: Insurance collection and verification"""
        print("\n🏥 Insurance Information")
        print("=" * 30)
        
        # Check if returning patient already has insurance
        if (self.appointment_data['patient_type'] == 'returning' and 
            self.appointment_data.get('insurance_carrier') and 
            str(self.appointment_data['insurance_carrier']).lower() not in ['none', 'nan', '']):
            
            print(f"✅ Using existing insurance: {self.appointment_data['insurance_carrier']}")
            
            # Ask if they want to update their insurance information
            update_insurance = input("Would you like to update your insurance information? (y/n): ").strip().lower()
            if update_insurance != 'y':
                print("✅ Keeping existing insurance information.")
                return
        
        # Get insurance carrier (for new patients or returning patients who want to update)
        while not self.appointment_data.get('insurance_carrier'):
            print("\nInsurance carriers available:")
            print("1) ICICI Lombard")
            print("2) HDFC Ergo")
            print("3) Star Health")
            print("4) Religare")
            print("5) New India Assurance")
            print("6) Self-pay/None")
            
            choice = input("Select your insurance carrier (1-6): ").strip()
            carriers = ["ICICI Lombard", "HDFC Ergo", "Star Health", "Religare", "New India Assurance", "None"]
            if choice.isdigit() and 1 <= int(choice) <= 6:
                self.appointment_data['insurance_carrier'] = carriers[int(choice)-1]
            else:
                print("❌ Please enter a valid choice (1-6).")
        
        # Get member ID if not self-pay
        if self.appointment_data['insurance_carrier'] != "None":
            while not self.appointment_data.get('insurance_member_id'):
                member_id = input("🆔 Please enter your insurance member ID: ").strip()
                if self.validate_insurance_id(member_id):
                    self.appointment_data['insurance_member_id'] = member_id
                else:
                    print("❌ Member ID should be 6-12 alphanumeric characters.")
            
            # Get group ID (optional)
            group_id = input("👥 Group ID (optional, press Enter to skip): ").strip()
            if group_id:
                self.appointment_data['insurance_group_id'] = group_id
        
        # Verify insurance
        if self.appointment_data['insurance_carrier'] != "None":
            print("\n🔍 Verifying insurance...")
            from backend.insurance import InsuranceInfo
            insurance_info = InsuranceInfo(
                carrier=str(self.appointment_data['insurance_carrier']),
                member_id=str(self.appointment_data['insurance_member_id']),
                group_number=str(self.appointment_data.get('insurance_group_id', ''))
            )
            
            success, details = self.insurance_validator.verify_insurance(insurance_info)
            if success:
                copay = details.get('copay', 'N/A')
                print(f"✅ Insurance verified successfully! Copay: {copay}")
            else:
                print("⚠️ Insurance verification failed, but we'll proceed.")
        else:
            print("✅ Self-pay selected.")
    
    def step5_appointment_confirmation(self):
        """Step 5: Appointment confirmation"""
        print("\n📋 Appointment Summary")
        print("=" * 30)
        print(f"👤 Patient: {self.appointment_data['patient_name']}")
        print(f"📅 DOB: {self.appointment_data['patient_dob']}")
        print(f"👨‍⚕️ Doctor: {self.appointment_data['doctor_preference']}")
        print(f"🏥 Location: {self.appointment_data['location_preference']}")
        print(f"📅 Date/Time: {self.appointment_data['appointment_datetime'].strftime('%A, %B %d, %Y at %I:%M %p')}")
        print(f"⏱️ Duration: {self.appointment_data['appointment_duration']} minutes")
        print(f"🏥 Insurance: {self.appointment_data.get('insurance_carrier', 'None')}")
        if self.appointment_data.get('insurance_member_id'):
            print(f"🆔 Member ID: {self.appointment_data['insurance_member_id']}")
        
        while True:
            confirm = input("\nDo you want to confirm this appointment? (yes/no): ").lower().strip()
            if confirm in ['yes', 'y']:
                return True
            elif confirm in ['no', 'n']:
                print("❌ Appointment cancelled.")
                return False
            else:
                print("❌ Please enter 'yes' or 'no'.")
    
    def step6_send_confirmation(self):
        """Step 6: Send confirmation via email and SMS"""
        print("\n📧 Sending confirmation...")
        
        # Generate appointment ID
        appointment_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.appointment_data['appointment_id'] = appointment_id
        
        # Update patient database with latest insurance information
        if self.appointment_data['patient_type'] == 'returning':
            try:
                # Update the patient's insurance information in the database
                self.patient_db.update_patient(
                    name=self.appointment_data['patient_name'],
                    dob=self.appointment_data['patient_dob'],
                    updates={
                        'Insurance': self.appointment_data.get('insurance_carrier', 'None'),
                        'Visit_Count': self.patient_db.get_visit_count(self.appointment_data['patient_name'], self.appointment_data['patient_dob']) + 1
                    }
                )
                print("✅ Patient record updated with latest insurance information.")
            except Exception as e:
                print(f"⚠️ Could not update patient record: {e}")
        else:
            # For new patients, update their insurance information
            try:
                self.patient_db.update_patient(
                    name=self.appointment_data['patient_name'],
                    dob=self.appointment_data['patient_dob'],
                    updates={
                        'Insurance': self.appointment_data.get('insurance_carrier', 'None'),
                        'Visit_Count': 1,
                        'Status': 'returning'
                    }
                )
                print("✅ New patient record updated with insurance information.")
            except Exception as e:
                print(f"⚠️ Could not update new patient record: {e}")
        
        # Prepare appointment data for services
        appt_data = {
            "appointment_id": appointment_id,
            "datetime": self.appointment_data['appointment_datetime'].isoformat(),
            "appointment_type": "New" if self.appointment_data['patient_type'] == 'new' else "Returning",
            "patient_data": {
                "name": self.appointment_data['patient_name'],
                "email": self.appointment_data['patient_email'],
                "insurance_carrier": self.appointment_data.get('insurance_carrier', 'None'),
                "insurance_member_id": self.appointment_data.get('insurance_member_id', ''),
                "insurance_group": self.appointment_data.get('insurance_group_id', ''),
            },
            "details": {
                "doctor": self.appointment_data['doctor_preference'],
                "location": self.appointment_data['location_preference'],
                "duration": f"{self.appointment_data['appointment_duration']} minutes",
            },
        }
        
        # Send email confirmation
        try:
            email_result = self.email_service.send_confirmation_email(appt_data)
            if email_result and email_result.get('success'):
                print("✅ Confirmation email sent successfully!")
            else:
                print("⚠️ Email confirmation sent (check logs for details)")
        except Exception as e:
            print(f"⚠️ Email sending failed: {e}")
        
        # Send SMS confirmation
        try:
            reminder = SMSReminder(
                patient_phone=self.appointment_data['patient_phone'],
                patient_name=self.appointment_data['patient_name'],
                appointment_date=self.appointment_data['appointment_datetime'],
                appointment_time=self.appointment_data['appointment_datetime'].strftime("%I:%M %p"),
                doctor_name=self.appointment_data['doctor_preference'],
                stage=ReminderStage.FIRST,
                appointment_id=appointment_id
            )
            sms_result = self.sms_service.send_reminder(reminder)
            if isinstance(sms_result, dict) and sms_result.get('success'):
                print("✅ Confirmation SMS sent successfully!")
            else:
                print("⚠️ SMS confirmation sent (check logs for details)")
        except Exception as e:
            print(f"⚠️ SMS sending failed: {e}")
        
        # Book the appointment
        try:
            if self.appointment_data.get('selected_slot'):
                patient_info = {
                    "name": self.appointment_data['patient_name'],
                    "email": self.appointment_data['patient_email'],
                    "insurance_carrier": self.appointment_data.get('insurance_carrier', 'None'),
                    "doctor_name": self.appointment_data['doctor_preference'],
                    "location": self.appointment_data['location_preference'],
                    "appointment_type": f"{self.appointment_data['patient_type']}_patient"
                }
                self.calendly.book_slot(self.appointment_data['selected_slot'], patient_info)
                print("✅ Appointment booked in calendar!")
        except Exception as e:
            print(f"⚠️ Calendar booking failed: {e}")
    
    def step7_schedule_reminders(self):
        """Step 7: Schedule 3-stage reminder system"""
        print("\n⏰ Scheduling reminders...")
        
        appointment_data = {
            "appointment_id": self.appointment_data.get('appointment_id', datetime.now().strftime("%Y%m%d%H%M%S")),
            "patient_name": self.appointment_data['patient_name'],
            "patient_email": self.appointment_data['patient_email'],
            "patient_phone": self.appointment_data['patient_phone'],
            "appointment_datetime": self.appointment_data['appointment_datetime'],
            "doctor_name": self.appointment_data['doctor_preference'],
            "location": self.appointment_data['location_preference'],
            "appointment_duration": self.appointment_data['appointment_duration']
        }
        
        try:
            self.reminder_system.schedule_appointment_reminders(appointment_data)
            print("✅ 3-stage reminder system scheduled!")
            print("   📧 Reminder 1: Confirmation + Intake Forms (sent now)")
            print("   📋 Reminder 2: Forms & Attendance Check (1 day before)")
            print("   ✅ Reminder 3: Final Confirmation (2 hours before)")
            print("\nNote: Reply with 'Appointment - Cancel' via SMS or email to cancel.")
        except Exception as e:
            print(f"⚠️ Reminder scheduling failed: {e}")
    
    def step8_export_data(self, appointment_data: dict):
        """Step 8: Export appointment data to Excel"""
        print("\n📊 Exporting appointment data...")
        
        import pandas as pd
        from pathlib import Path
        
        export_path = Path("data/exports/appointments.xlsx")
        export_path.parent.mkdir(parents=True, exist_ok=True)
        
        appointment_record = {
            "patient_name": appointment_data.get('patient_name'),
            "patient_dob": appointment_data.get('patient_dob'),
            "patient_email": appointment_data.get('patient_email'),
            "patient_phone": appointment_data.get('patient_phone'),
            "patient_type": appointment_data.get('patient_type'),
            "doctor": appointment_data.get('doctor_preference'),
            "location": appointment_data.get('location'),
            "appointment_datetime": appointment_data.get('appointment_datetime'),
            "duration_minutes": appointment_data.get('appointment_duration'),
            "insurance_carrier": appointment_data.get('insurance_carrier', 'None'),
            "insurance_member_id": appointment_data.get('insurance_member_id', ''),
            "insurance_group_id": appointment_data.get('insurance_group_id', ''),
            "appointment_status": "confirmed",
            "forms_sent": True,
            "reminders_scheduled": True,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            df = pd.DataFrame([appointment_record])
            if export_path.exists():
                existing = pd.read_excel(export_path)
                df = pd.concat([existing, df], ignore_index=True)
            df.to_excel(export_path, index=False)
            print(f"✅ Appointment data exported to {export_path}")
        except Exception as e:
            print(f"⚠️ Export failed: {e}")
    
    def run(self):
        """Run the complete interactive workflow"""
        try:
            # Step 1: Greeting and collect info
            self.step1_greeting_and_collect_info()
            
            # Step 2: Patient lookup
            self.step2_patient_lookup()
            
            # Step 3: Smart scheduling
            if not self.step3_smart_scheduling():
                return
            
            # Step 4: Insurance collection
            self.step4_insurance_collection()
            
            # Step 5: Appointment confirmation
            if not self.step5_appointment_confirmation():
                return
            
            # Step 6: Send confirmation
            self.step6_send_confirmation()
            
            # Step 7: Schedule reminders
            self.step7_schedule_reminders()
            
            # Step 8: Export data
            self.step8_export_data()
            
            print("\n🎉 Appointment scheduling completed successfully!")
            print("Thank you for using our medical scheduling system!")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            print("Please try again or contact support.")

def main():
    """Main function"""
    # Get API key
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("❌ GROQ_API_KEY not found in environment variables.")
        print("Please set GROQ_API_KEY in your environment.")
        return
    
    # Create and run agent
    agent = InteractiveMedicalAgent(groq_api_key)
    agent.run()

if __name__ == "__main__":
    main()
