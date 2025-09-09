# 🏥 Medical Scheduling Agent - MVP-1

A fully functional AI-powered medical appointment scheduling system that orchestrates the complete workflow from patient greeting to appointment confirmation and reminders.

## ✨ Features

- **End-to-End Workflow**: Complete 8-stage appointment scheduling process
- **AI-Powered**: Uses Groq's Mixtral model for natural conversation
- **Multi-Service Integration**: Calendly, Twilio, Email, Insurance verification
- **Robust Validation**: DOB, insurance ID, slot selection validation
- **Mock Mode**: Works without external APIs for testing
- **5 Specialized Doctors**: Dr. Sharma, Dr. Iyer, Dr. Mehta, Dr. Kapoor, Dr. Reddy
- **3-Stage Reminders**: Email and SMS reminders with no-show handling
- **Excel Logging**: Complete audit trail and reporting

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment
Create a `.env` file with your API keys:
```env
GROQ_API_KEY=your_groq_api_key_here
# Optional: CALENDLY_API_KEY, TWILIO_*, SMTP_*
```

### 3. Test the System
```bash
python test_agent_imports.py
```

### 4. Run the Agent
```bash
python run_agent.py
```

## 📋 Workflow

1. **Patient Greeting** → Collect basic information
2. **Patient Lookup** → Determine new vs returning patient
3. **Smart Scheduling** → Show available slots (60min new, 30min returning)
4. **Insurance Collection** → Collect and verify insurance details
5. **Appointment Confirmation** → Confirm booking and send notifications
6. **Form Distribution** → Email intake forms
7. **Reminder System** → Schedule 3-stage reminders
8. **Admin Review** → Export data for reporting

## 🏗️ Architecture

```
backend/
├── agent.py              # Main AI agent (LangGraph workflow)
├── patient_lookup.py     # Patient database management
├── insurance.py          # Insurance verification
├── remainders.py         # 3-stage reminder system
├── schedular.py          # Doctor scheduling logic
└── integrations/
    ├── calendly_service.py  # Appointment booking
    ├── email_service.py     # Email notifications
    └── sms_service.py       # SMS reminders
```

## 🔧 Services

- **PatientDatabase**: CSV-based patient lookup and management
- **CalendlyService**: Real Calendly API or mock scheduling
- **EmailService**: SMTP email with intake forms
- **SMSService**: Twilio SMS or mock notifications
- **ReminderSystem**: Automated 3-stage reminder workflow
- **InsuranceValidator**: Insurance verification and validation

## 📊 Data Files

- `data/patients.csv` - Patient database
- `data/doctor_schedules.xlsx` - Doctor availability and bookings
- `data/exports/appointments.xlsx` - Appointment logs
- `data/insurance_verifications.json` - Insurance records

## 🎯 Key Features

### Validation
- **DOB Format**: MM/DD/YYYY validation
- **Insurance ID**: 6-12 alphanumeric characters
- **Slot Selection**: Must choose from available options
- **Insurance Carriers**: Normalized to standard names

### Mock Mode
- Works without external APIs
- Generates realistic test data
- Logs all actions to console
- Perfect for development and testing

### Error Handling
- Graceful fallbacks for missing services
- User-friendly error messages
- Retry mechanisms for failed operations
- Comprehensive logging

## 📖 Documentation

- [AGENT_USAGE.md](AGENT_USAGE.md) - Detailed usage guide
- [requirements.txt](requirements.txt) - Python dependencies

## 🛠️ Development

### Testing
```bash
# Test all imports
python test_agent_imports.py

# Test individual components
python backend/insurance.py
python backend/remainders.py
```

### Adding New Features
1. Modify the workflow in `backend/agent.py`
2. Add new services in `backend/integrations/`
3. Update validation rules as needed
4. Test with `python test_agent_imports.py`

## 📞 Support

For issues or questions:
1. Run the test script to verify setup
2. Check the usage guide for detailed instructions
3. Ensure all dependencies are installed
4. Verify environment variables are set

## 🎉 Status

✅ **MVP-1 Complete** - All core functionality implemented and tested
- End-to-end workflow working
- All backend services integrated
- Mock mode fully functional
- Data validation implemented
- Excel logging operational
- Ready for production use with real API keys
