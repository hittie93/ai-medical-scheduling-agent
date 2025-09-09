# 🏥 Streamlit Medical Scheduling System

A modern web interface for the Medical Scheduling System built with Streamlit, replicating the exact workflow from `interactive_agent.py`.

## 🚀 Quick Start

### 1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2. **Set Up Environment Variables**
Create a `.env` file in the project root:
```env
GROQ_API_KEY=your_groq_api_key
SMTP_USERNAME=your_sendgrid_username
SMTP_PASSWORD=your_sendgrid_password
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_FROM_EMAIL=your_email@domain.com
TWILIO_ACCOUNT_SID1=your_twilio_sid
TWILIO_AUTH_TOKEN1=your_twilio_token
TWILIO_PHONE_NUMBER1=your_twilio_phone
```

### 3. **Launch the App**

**Option A: Using the launcher script**
```bash
python run_streamlit.py
```

**Option B: Direct Streamlit command**
```bash
streamlit run streamlit_app.py
```

**Option C: With custom port**
```bash
streamlit run streamlit_app.py --server.port 8502
```

## 📋 **Workflow Steps**

The Streamlit app follows the exact same 8-step workflow as `interactive_agent.py`:

### **Step 1: Patient Information** 👤
- **Full Name**: Enter patient's complete name
- **Date of Birth**: Format MM/DD/YYYY (e.g., 01/09/2004)
- **Phone Number**: Include country code (e.g., +91 9542328970)
- **Email Address**: Valid email for confirmations
- **Doctor Selection**: Choose from 5 specialized doctors:
  - Dr. Sharma - General Medicine
  - Dr. Iyer - Cardiology
  - Dr. Mehta - Orthopedics
  - Dr. Kapoor - Dermatology
  - Dr. Reddy - Pediatrics
- **Location**: Preferred clinic location

### **Step 2: Patient Lookup** 🔍
- **Automatic lookup** based on name and DOB
- **New Patient**: 60-minute appointment, insurance collection required
- **Returning Patient**: 30-minute appointment, uses existing insurance if available
- **Database integration** with `patients.csv`

### **Step 3: Smart Scheduling** 📅
- **Available slots** displayed in user-friendly format
- **Real-time availability** checking with `CalendlyService`
- **Duration-based slots**: 30min for returning, 60min for new patients
- **Calendar integration** with `data/appointments.xlsx`

### **Step 4: Insurance Collection** 🏥
- **Returning patients**: Option to update existing insurance
- **New patients**: Required insurance information
- **Carrier selection**: 6 predefined options + self-pay
- **Member ID validation**: 6-12 alphanumeric characters
- **Group ID**: Optional field
- **Real-time verification** with `InsuranceValidator`

### **Step 5: Appointment Confirmation** 📋
- **Complete summary** of all appointment details
- **Review all information** before final confirmation
- **Clear display** of patient, doctor, time, and insurance details

### **Step 6: Send Confirmation** 📧
- **Email confirmation** with appointment details
- **SMS confirmation** via Twilio
- **Calendar booking** in `data/appointments.xlsx`
- **Patient database update** with latest information

### **Step 7: Schedule Reminders** ⏰
- **3-stage reminder system**:
  - **R1 (Immediate)**: Confirmation + Intake Forms
  - **R2 (1 day before)**: Forms & Attendance Check
  - **R3 (2 hours before)**: Final Confirmation
- **Background scheduling** with `APScheduler`
- **Cancellation support** via SMS/email replies

### **Step 8: Export Data** 📊
- **Excel export** to `data/exports/appointments.xlsx`
- **Complete audit trail** of all appointments
- **Success confirmation** with celebration animation

## 🎨 **Features**

### **Modern UI/UX**
- **Clean, professional design** with medical theme
- **Step-by-step progress** indicator in sidebar
- **Responsive layout** that works on all devices
- **Real-time validation** and error handling
- **Success animations** and feedback

### **Smart Workflow**
- **Context-aware** steps based on patient type
- **Data persistence** across steps using session state
- **Automatic validation** of all inputs
- **Error recovery** with helpful messages

### **Integration Features**
- **Real email/SMS** sending (not mock)
- **Background processes** for email cancellation checking
- **Excel logging** for all appointments
- **Insurance verification** with real validation

## 🔧 **Technical Details**

### **Architecture**
- **Streamlit** for web interface
- **Session state** for data persistence
- **Modular design** reusing existing backend services
- **Error handling** with user-friendly messages

### **Backend Integration**
- **`InteractiveMedicalAgent`** as core logic
- **All existing services** (Email, SMS, Calendar, etc.)
- **Database operations** with `PatientDatabase`
- **Scheduling** with `CalendlyService` and `Scheduler`

### **Data Flow**
1. **User input** → Session state
2. **Session state** → Backend services
3. **Backend services** → Database/APIs
4. **Results** → User feedback

## 🚨 **Troubleshooting**

### **Common Issues**

1. **"GROQ_API_KEY not found"**
   - Ensure `.env` file exists with valid API key
   - Check file location (should be in project root)

2. **"Module not found" errors**
   - Run `pip install -r requirements.txt`
   - Ensure virtual environment is activated

3. **Email/SMS not sending**
   - Verify SMTP credentials in `.env`
   - Check Twilio credentials for SMS
   - Test with real credentials (not mock mode)

4. **Calendar slots not showing**
   - Check `data/appointments.xlsx` exists
   - Verify doctor schedules in `backend/schedular.py`

### **Debug Mode**
Run with debug information:
```bash
streamlit run streamlit_app.py --logger.level debug
```

## 📱 **Usage Examples**

### **New Patient Flow**
1. Enter personal information
2. Select doctor (e.g., Dr. Iyer - Cardiology)
3. System detects "new patient" → 60-minute appointment
4. Choose from available slots
5. Select insurance carrier and enter details
6. Verify insurance information
7. Confirm appointment
8. Receive email + SMS confirmation
9. 3-stage reminders scheduled
10. Data exported to Excel

### **Returning Patient Flow**
1. Enter personal information
2. Select doctor
3. System detects "returning patient" → 30-minute appointment
4. Uses existing insurance (if available)
5. Option to update insurance information
6. Choose from available slots
7. Confirm appointment
8. Receive confirmations
9. Reminders scheduled
10. Data exported

## 🎯 **Key Benefits**

- **User-friendly**: No command-line interface needed
- **Professional**: Clean, medical-themed design
- **Comprehensive**: All features from CLI version
- **Reliable**: Real email/SMS integration
- **Scalable**: Easy to deploy and maintain
- **Accessible**: Works on any device with browser

## 🔄 **Migration from Gradio**

The Streamlit app replaces the previous Gradio interface with:
- **Better UX**: More intuitive step-by-step flow
- **Cleaner code**: Easier to maintain and extend
- **Better integration**: Seamless backend service integration
- **Professional look**: Medical-appropriate styling
- **Mobile-friendly**: Responsive design

## 📞 **Support**

For issues or questions:
1. Check the troubleshooting section above
2. Verify all environment variables are set
3. Test with the CLI version first (`python interactive_agent.py`)
4. Check logs for detailed error messages

---

**Ready to use!** 🚀 Run `python run_streamlit.py` to start the Medical Scheduling System.
