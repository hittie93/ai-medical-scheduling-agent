#!/usr/bin/env python3
"""
Test script to verify email and SMS services configuration
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_services():
    """Test email and SMS services configuration"""
    print("🧪 Testing Medical Scheduling Agent Services")
    print("=" * 50)
    
    # Check environment variables
    print("\n📋 Environment Variables:")
    print(f"GROQ_API_KEY: {'✅ Set' if os.getenv('GROQ_API_KEY') else '❌ Not set'}")
    print(f"SMTP_USERNAME: {'✅ Set' if os.getenv('SMTP_USERNAME') else '❌ Not set'}")
    print(f"SMTP_PASSWORD: {'✅ Set' if os.getenv('SMTP_PASSWORD') else '❌ Not set'}")
    print(f"TWILIO_ACCOUNT_SID: {'✅ Set' if os.getenv('TWILIO_ACCOUNT_SID') else '❌ Not set'}")
    print(f"TWILIO_AUTH_TOKEN: {'✅ Set' if os.getenv('TWILIO_AUTH_TOKEN') else '❌ Not set'}")
    print(f"TWILIO_ACCOUNT_SID1: {'✅ Set' if os.getenv('TWILIO_ACCOUNT_SID1') else '❌ Not set'}")
    print(f"TWILIO_AUTH_TOKEN1: {'✅ Set' if os.getenv('TWILIO_AUTH_TOKEN1') else '❌ Not set'}")
    print(f"TWILIO_PHONE_NUMBER1: {'✅ Set' if os.getenv('TWILIO_PHONE_NUMBER1') else '❌ Not set'}")
    
    # Test Email Service
    print("\n📧 Testing Email Service:")
    try:
        from backend.integrations.email_service import EmailService
        
        smtp_config = {
            'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('SMTP_USERNAME'),
            'password': os.getenv('SMTP_PASSWORD'),
            'from_email': os.getenv('SMTP_FROM_EMAIL', os.getenv('SMTP_USERNAME'))
        }
        
        use_real_email = bool(smtp_config['username'] and smtp_config['password'])
        email_service = EmailService(smtp_config=smtp_config, use_mock=not use_real_email)
        
        print(f"   Status: {'Real SMTP' if use_real_email else 'Mock Mode'}")
        
        # Test sending a simple email
        test_data = {
            "appointment_id": "TEST123",
            "datetime": "2024-01-15T10:00:00",
            "patient_data": {
                "name": "Test Patient",
                "email": "test@example.com"
            },
            "details": {
                "doctor": "Dr. Test",
                "location": "Test Clinic"
            }
        }
        
        result = email_service.send_confirmation_email(test_data)
        print(f"   Test Result: {'✅ Success' if result and result.get('success') else '⚠️ Check logs'}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test SMS Service
    print("\n📱 Testing SMS Service:")
    try:
        from backend.integrations.sms_service import SMSService, SMSReminder, ReminderStage
        from datetime import datetime
        
        twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID1')
        twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN1')
        twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER1')
        
        use_real_sms = bool(twilio_account_sid and twilio_auth_token and twilio_phone_number)
        sms_service = SMSService(
            account_sid=twilio_account_sid,
            auth_token=twilio_auth_token,
            from_number=twilio_phone_number,
            mock_mode=not use_real_sms
        )
        
        print(f"   Status: {'Real Twilio' if use_real_sms else 'Mock Mode'}")
        
        # Test sending a simple SMS
        reminder = SMSReminder(
            patient_phone="+1234567890",  # Test number
            patient_name="Test Patient",
            appointment_date=datetime.now(),
            appointment_time="10:00 AM",
            doctor_name="Dr. Test",
            stage=ReminderStage.FIRST,
            appointment_id="TEST123"
        )
        
        result = sms_service.send_reminder(reminder)
        print(f"   Test Result: {'✅ Success' if isinstance(result, dict) and result.get('success') else '⚠️ Check logs'}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎯 Summary:")
    print("   - Add missing environment variables to your .env file")
    print("   - Check CONFIGURATION_GUIDE.md for setup instructions")
    print("   - Run 'python interactive_agent.py' to start the agent")

if __name__ == "__main__":
    test_services()
