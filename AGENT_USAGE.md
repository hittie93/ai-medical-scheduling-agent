# Medical Scheduling Agent - Usage Guide

## 🏥 Overview
The Medical Scheduling Agent is a fully functional AI-powered system that orchestrates medical appointment scheduling end-to-end. It integrates with various backend services to provide a complete workflow from patient greeting to appointment confirmation and reminders.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables
Create a `.env` file in the project root with your API keys:
```env
# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional (will use mock mode if not provided)
CALENDLY_API_KEY=your_calendly_api_key_here
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email_here
SMTP_PASSWORD=your_app_password_here
```

### 3. Test the System
```bash
python test_agent_imports.py
```

### 4. Run the Agent
```bash
streamlit_runrun streamlit_app.py
```

## 🔧 Available Services

### Core Services
- **PatientDatabase** - Patient lookup and management
- **CalendlyService** - Appointment scheduling (real API or mock mode)
- **EmailService** - Email notifications and forms
- **SMSService** - SMS reminders (real Twilio or mock mode)
- **ReminderSystem** - 3-stage reminder workflow
- **InsuranceValidator** - Insurance verification

### Data Files
- `data/patients.csv` - Patient database
- `data/doctor_schedules.xlsx` - Doctor availability and bookings
- `data/exports/appointments.xlsx` - Appointment logs
- `data/insurance_verifications.json` - Insurance verification records

## 📋 Workflow Steps

The agent follows an 8-stage workflow:

1. **Patient Greeting** - Welcome and collect basic info
2. **Patient Lookup** - Check if new or returning patient
3. **Smart Scheduling** - Show available slots (60min new, 30min returning)
4. **Insurance Collection** - Collect and verify insurance details
5. **Appointment Confirmation** - Confirm booking and send notifications
6. **Form Distribution** - Email intake forms
7. **Reminder System** - Schedule 3-stage reminders
8. **Admin Review** - Export data for reporting

## 👨‍⚕️ Available Doctors

The system supports 5 specialized doctors:
1. **Dr. Sharma** - General Medicine
2. **Dr. Iyer** - Cardiology
3. **Dr. Mehta** - Orthopedics
4. **Dr. Kapoor** - Dermatology
5. **Dr. Reddy** - Pediatrics

## 🔍 Data Validation

The system includes robust validation for:
- **DOB Format**: MM/DD/YYYY (e.g., 03/15/1995)
- **Insurance ID**: 6-12 alphanumeric characters
- **Slot Selection**: Must choose from available options
- **Insurance Carriers**: Normalized to standard names

## 📊 Mock Mode Features

When external APIs are not available, the system runs in mock mode:
- **CalendlyService**: Generates realistic appointment slots
- **SMSService**: Logs SMS messages to console
- **EmailService**: Logs email content to console
- **InsuranceValidator**: Uses mock verification data

## 🛠️ Troubleshooting

### Common Issues

1. **Import Errors**: Run `python test_agent_imports.py` to verify all modules
2. **API Key Errors**: Ensure GROQ_API_KEY is set in your environment
3. **Data File Errors**: The system will create missing files automatically
4. **Unicode Errors**: The system uses ASCII-compatible characters for Windows

### Testing Individual Components

```bash
# Test patient lookup
python -c "from backend.patient_lookup import PatientDatabase; db = PatientDatabase(); print(db.search_patient('John Doe', '01/01/1990'))"

# Test insurance validation
python backend/insurance.py

# Test reminder system
python backend/remainders.py
```

## 📁 Project Structure

```
RagaAI Assignment/
├── backend/
│   ├── agent.py              # Main AI agent
│   ├── patient_lookup.py     # Patient database
│   ├── insurance.py          # Insurance validation
│   ├── remainders.py         # Reminder system
│   ├── schedular.py          # Scheduling logic
│   └── integrations/
│       ├── calendly_service.py
│       ├── email_service.py
│       └── sms_service.py
├── data/
│   ├── patients.csv
│   ├── doctor_schedules.xlsx
│   └── exports/
├── run_agent.py              # Entry point
├── test_agent_imports.py     # Test script
└── requirements.txt
```

## 🎯 Next Steps

1. **Add Real API Keys**: Set up actual Groq, Calendly, and Twilio accounts
2. **Customize Doctors**: Modify doctor specialties and schedules in `schedular.py`
3. **Add UI**: Create a Streamlit or Gradio interface
4. **Extend Validation**: Add more insurance carriers or validation rules
5. **Reporting**: Enhance Excel export with more detailed analytics

## 📞 Support

For issues or questions:
1. Check the test script output: `python test_agent_imports.py`
2. Verify all dependencies are installed: `pip list`
3. Ensure data files exist in the `data/` directory
4. Check environment variables are set correctly
