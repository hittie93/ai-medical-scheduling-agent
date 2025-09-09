#!/usr/bin/env python3
"""
Streamlit Medical Scheduling System
Replicates the exact workflow from interactive_agent.py
"""

import streamlit as st
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.patient_lookup import PatientDatabase
from backend.integrations.calendly_service import CalendlyService
from backend.integrations.email_service import EmailService
from backend.integrations.sms_service import SMSService
from backend.remainders import ReminderSystem
from backend.insurance import InsuranceValidator
from backend.schedular import Scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from backend.email_cancellation import check_email_cancellations

# Initialize session state
if 'current_step' not in st.session_state:
    st.session_state.current_step = 1
    st.session_state.appointment_data = {}
    st.session_state.agent = None
    st.session_state.scheduler = None

def initialize_agent():
    """Initialize the medical agent"""
    if st.session_state.agent is None:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            st.error("❌ GROQ_API_KEY not found in environment variables.")
            st.stop()
        
        # Initialize agent
        from interactive_agent import InteractiveMedicalAgent
        st.session_state.agent = InteractiveMedicalAgent(groq_api_key)
        
        # Initialize background scheduler for email cancellations
        if st.session_state.scheduler is None:
            st.session_state.scheduler = BackgroundScheduler()
            st.session_state.scheduler.add_job(
                check_email_cancellations,
                'interval',
                minutes=1,
                id='email_cancellation_checker'
            )
            st.session_state.scheduler.start()

def step1_greeting_and_collect_info():
    """Step 1: Greeting and collect patient information"""
    st.markdown("## 🏥 Welcome to our Medical Scheduling System!")
    st.markdown("=" * 50)
    
    with st.form("patient_info_form"):
        st.markdown("### 👤 Patient Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Full Name", placeholder="Enter your full name")
            dob = st.text_input("Date of Birth (MM/DD/YYYY)", placeholder="MM/DD/YYYY")
        
        with col2:
            phone = st.text_input("Phone Number", placeholder="+91 954XXXXXXX")
            email = st.text_input("Email Address", placeholder="your.email@example.com")
        
        st.markdown("### 👨‍⚕️ Doctor Selection")
        st.markdown("Choose your preferred doctor:")
        
        doctors = [
            "Dr. Sharma - General Medicine",
            "Dr. Iyer - Cardiology", 
            "Dr. Mehta - Orthopedics",
            "Dr. Kapoor - Dermatology",
            "Dr. Reddy - Pediatrics"
        ]
        
        doctor_choice = st.selectbox("Select Doctor", range(1, 6), format_func=lambda x: f"{x}) {doctors[x-1]}")
        doctor_name = doctors[doctor_choice - 1].split(" - ")[0]
        
        location = st.text_input("Preferred Clinic Location", value="Main", placeholder="Enter clinic location")
        
        submitted = st.form_submit_button("Continue to Patient Lookup", type="primary")
        
        if submitted:
            if not all([name, dob, phone, email]):
                st.error("❌ Please fill in all required fields.")
                return False
            
            # Validate DOB format
            try:
                datetime.strptime(dob, "%m/%d/%Y")
            except ValueError:
                st.error("❌ Please enter date of birth in MM/DD/YYYY format.")
                return False
            
            # Store patient info
            st.session_state.appointment_data = {
                'patient_name': name,
                'patient_dob': dob,
                'patient_phone': phone,
                'patient_email': email,
                'doctor_preference': doctor_name,
                'location': location
            }
            
            st.session_state.current_step = 2
            st.rerun()
    
    return False

def step2_patient_lookup():
    """Step 2: Patient lookup"""
    st.markdown("## 🔍 Patient Lookup")
    st.markdown("=" * 30)
    
    # Perform patient lookup
    patient = st.session_state.agent.patient_db.search_patient(
        st.session_state.appointment_data['patient_name'],
        st.session_state.appointment_data['patient_dob']
    )
    
    if patient:
        st.session_state.appointment_data['patient_type'] = 'returning'
        st.session_state.appointment_data['appointment_duration'] = 30
        st.success(f"✅ Welcome back, {st.session_state.appointment_data['patient_name']}!")
        st.info("📋 You are a returning patient. Your appointment will be 30 minutes.")
        
        # Check existing insurance
        existing_insurance = patient.get('Insurance', 'None')
        if existing_insurance and str(existing_insurance).lower() not in ['none', 'nan', '']:
            st.session_state.appointment_data['insurance_carrier'] = str(existing_insurance)
            st.info(f"🏥 Using your existing insurance: {existing_insurance}")
        else:
            st.info("🏥 No insurance on file. We'll collect this information.")
    else:
        st.session_state.appointment_data['patient_type'] = 'new'
        st.session_state.appointment_data['appointment_duration'] = 60
        st.success(f"👋 Welcome, {st.session_state.appointment_data['patient_name']}!")
        st.info("📋 You are a new patient. Your first appointment will be 60 minutes.")
        st.info("🏥 We'll need to collect your insurance information.")
        
        # Add new patient to database
        st.session_state.agent.patient_db.add_patient({
            "name": st.session_state.appointment_data['patient_name'],
            "dob": st.session_state.appointment_data['patient_dob'],
            "email": st.session_state.appointment_data['patient_email'],
            "phone": st.session_state.appointment_data['patient_phone'],
            "doctor": st.session_state.appointment_data['doctor_preference']
        })
    
    if st.button("Continue to Scheduling", type="primary"):
        st.session_state.current_step = 3
        st.rerun()

def step3_smart_scheduling():
    """Step 3: Smart scheduling"""
    st.markdown("## 📅 Smart Scheduling")
    st.markdown("=" * 30)
    
    doctor = st.session_state.appointment_data['doctor_preference']
    duration = st.session_state.appointment_data['appointment_duration']
    
    st.info(f"📅 Finding available slots with {doctor}...")
    
    # Get available slots
    try:
        # Convert doctor name to doctor_id
        doctor_mapping = {
            "Dr. Sharma": "dr_sharma",
            "Dr. Iyer": "dr_iyer", 
            "Dr. Mehta": "dr_mehta",
            "Dr. Kapoor": "dr_kapoor",
            "Dr. Reddy": "dr_reddy"
        }
        doctor_id = doctor_mapping.get(doctor, "dr_sharma")
        
        slots = st.session_state.agent.calendly.get_available_slots(
            doctor_id=doctor_id,
            date_from=datetime.now(),
            date_to=datetime.now() + timedelta(days=7),
            duration_minutes=duration
        )
        
        if not slots:
            st.error("❌ No available slots found. Please try a different doctor or contact support.")
            return False
        
        st.success(f"📋 Available slots for {duration}-minute appointment:")
        
        # Display slots in a nice format
        slot_options = []
        slot_data = []  # Store parsed slot data
        
        for i, slot in enumerate(slots, 1):
            # Parse datetime to get date and time
            dt = datetime.fromisoformat(slot['datetime'])
            date_str = dt.strftime('%A, %B %d, %Y')
            time_str = dt.strftime('%I:%M %p')
            slot_text = f"{i}. {date_str} at {time_str}"
            slot_options.append(slot_text)
            slot_data.append({
                'date_str': date_str,
                'time_str': time_str,
                'datetime': slot['datetime']
            })
        
        selected_slot_idx = st.selectbox(
            "Select a slot:",
            range(len(slots)),
            format_func=lambda x: slot_options[x]
        )
        
        selected_slot = slots[selected_slot_idx]
        selected_data = slot_data[selected_slot_idx]
        
        st.success(f"✅ Selected: {selected_data['date_str']} at {selected_data['time_str']}")
        
        # Store selected slot
        st.session_state.appointment_data.update({
            'appointment_date': selected_data['date_str'],
            'appointment_time': selected_data['time_str'],
            'appointment_datetime': selected_data['datetime']
        })
        
        if st.button("Continue to Insurance", type="primary"):
            st.session_state.current_step = 4
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error getting available slots: {str(e)}")
        return False
    
    return True

def step4_insurance_collection():
    """Step 4: Insurance collection"""
    st.markdown("## 🏥 Insurance Information")
    st.markdown("=" * 30)
    
    # Check if returning patient already has insurance
    if (st.session_state.appointment_data['patient_type'] == 'returning' and 
        st.session_state.appointment_data.get('insurance_carrier') and 
        str(st.session_state.appointment_data['insurance_carrier']).lower() not in ['none', 'nan', '']):
        
        st.success(f"✅ Using existing insurance: {st.session_state.appointment_data['insurance_carrier']}")
        
        update_insurance = st.radio(
            "Would you like to update your insurance information?",
            ["No", "Yes"],
            index=0
        )
        
        if update_insurance == "No":
            st.info("✅ Keeping existing insurance information.")
            if st.button("Continue to Confirmation", type="primary"):
                st.session_state.current_step = 5
                st.rerun()
            return
    
    # Insurance carrier selection
    st.markdown("### Insurance carriers available:")
    carriers = [
        "ICICI Lombard",
        "HDFC Ergo", 
        "Star Health",
        "Religare",
        "New India Assurance",
        "Self-pay/None"
    ]
    
    carrier_choice = st.selectbox("Select your insurance carrier:", range(1, 7), format_func=lambda x: f"{x}) {carriers[x-1]}")
    selected_carrier = carriers[carrier_choice - 1]
    
    st.session_state.appointment_data['insurance_carrier'] = selected_carrier
    
    # Member ID and Group ID
    if selected_carrier != "Self-pay/None":
        member_id = st.text_input("🆔 Insurance Member ID", placeholder="Enter 6-12 alphanumeric characters")
        group_id = st.text_input("👥 Group ID (optional)", placeholder="Enter group ID or leave blank")
        
        if member_id:
            # Validate member ID
            if st.session_state.agent.validate_insurance_id(member_id):
                st.session_state.appointment_data['insurance_member_id'] = member_id
                if group_id:
                    st.session_state.appointment_data['insurance_group_id'] = group_id
            else:
                st.error("❌ Member ID should be 6-12 alphanumeric characters.")
                return
    
    # Verify insurance
    if selected_carrier != "Self-pay/None" and st.session_state.appointment_data.get('insurance_member_id'):
        if st.button("🔍 Verify Insurance", type="secondary"):
            with st.spinner("Verifying insurance..."):
                from backend.insurance import InsuranceInfo
                insurance_info = InsuranceInfo(
                    carrier=str(st.session_state.appointment_data['insurance_carrier']),
                    member_id=str(st.session_state.appointment_data['insurance_member_id']),
                    group_number=str(st.session_state.appointment_data.get('insurance_group_id', ''))
                )
                
                success, details = st.session_state.agent.insurance_validator.verify_insurance(insurance_info)
                if success:
                    copay = details.get('copay', 'N/A')
                    st.success(f"✅ Insurance verified successfully! Copay: {copay}")
                else:
                    st.warning("⚠️ Insurance verification failed, but we'll proceed.")
    
    if st.button("Continue to Confirmation", type="primary"):
        st.session_state.current_step = 5
        st.rerun()

def step5_appointment_confirmation():
    """Step 5: Appointment confirmation"""
    st.markdown("## 📋 Appointment Summary")
    st.markdown("=" * 30)
    
    # Display appointment summary
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**👤 Patient:** {st.session_state.appointment_data['patient_name']}")
        st.markdown(f"**📅 DOB:** {st.session_state.appointment_data['patient_dob']}")
        st.markdown(f"**👨‍⚕️ Doctor:** {st.session_state.appointment_data['doctor_preference']}")
        st.markdown(f"**🏥 Location:** {st.session_state.appointment_data['location']}")
    
    with col2:
        st.markdown(f"**📅 Date/Time:** {st.session_state.appointment_data['appointment_date']} at {st.session_state.appointment_data['appointment_time']}")
        st.markdown(f"**⏱️ Duration:** {st.session_state.appointment_data['appointment_duration']} minutes")
        st.markdown(f"**🏥 Insurance:** {st.session_state.appointment_data.get('insurance_carrier', 'None')}")
        if st.session_state.appointment_data.get('insurance_member_id'):
            st.markdown(f"**🆔 Member ID:** {st.session_state.appointment_data['insurance_member_id']}")
    
    confirm = st.radio(
        "Do you want to confirm this appointment?",
        ["No", "Yes"],
        index=0
    )
    
    if confirm == "Yes":
        if st.button("Confirm Appointment", type="primary"):
            st.session_state.current_step = 6
            st.rerun()
    else:
        st.info("Please review your appointment details and confirm when ready.")

def step6_send_confirmation():
    """Step 6: Send confirmation"""
    st.markdown("## 📧 Sending Confirmation")
    st.markdown("=" * 30)
    
    with st.spinner("Sending confirmation..."):
        try:
            # Generate appointment ID
            appointment_id = datetime.now().strftime("%Y%m%d%H%M%S")
            st.session_state.appointment_data['appointment_id'] = appointment_id
            
            # Update patient database
            if st.session_state.appointment_data['patient_type'] == 'returning':
                st.session_state.agent.patient_db.update_patient(
                    name=st.session_state.appointment_data['patient_name'],
                    dob=st.session_state.appointment_data['patient_dob'],
                    updates={
                        'Insurance': st.session_state.appointment_data.get('insurance_carrier', 'None'),
                        'Visit_Count': st.session_state.agent.patient_db.get_visit_count(
                            st.session_state.appointment_data['patient_name'], 
                            st.session_state.appointment_data['patient_dob']
                        ) + 1
                    }
                )
            else:
                st.session_state.agent.patient_db.update_patient(
                    name=st.session_state.appointment_data['patient_name'],
                    dob=st.session_state.appointment_data['patient_dob'],
                    updates={
                        'Insurance': st.session_state.appointment_data.get('insurance_carrier', 'None'),
                        'Visit_Count': 1,
                        'Status': 'returning'
                    }
                )
            
            # Book appointment
            # Convert doctor name to doctor_id
            doctor_mapping = {
                "Dr. Sharma": "dr_sharma",
                "Dr. Iyer": "dr_iyer", 
                "Dr. Mehta": "dr_mehta",
                "Dr. Kapoor": "dr_kapoor",
                "Dr. Reddy": "dr_reddy"
            }
            doctor_id = doctor_mapping.get(st.session_state.appointment_data['doctor_preference'], "dr_sharma")
            
            slot_data = {
                'datetime': st.session_state.appointment_data['appointment_datetime'],
                'doctor_id': doctor_id,
                'duration_minutes': st.session_state.appointment_data['appointment_duration']
            }
            
            patient_info = {
                'name': st.session_state.appointment_data['patient_name'],
                'email': st.session_state.appointment_data['patient_email'],
                'insurance_carrier': st.session_state.appointment_data.get('insurance_carrier', 'None'),
                'doctor_name': st.session_state.appointment_data['doctor_preference'],
                'location': st.session_state.appointment_data['location'],
                'appointment_type': f"{st.session_state.appointment_data['patient_type']}_patient"
            }
            
            booking_result = st.session_state.agent.calendly.book_slot(slot_data, patient_info)
            
            if booking_result.get('success'):
                st.success("✅ Appointment booked in calendar!")
            else:
                st.warning("⚠️ Calendar booking failed, but proceeding with confirmation.")
            
            # Send email confirmation
            # Prepare appointment data in the correct format
            appt_data = {
                "appointment_id": appointment_id,
                "datetime": st.session_state.appointment_data['appointment_datetime'],
                "appointment_type": "New" if st.session_state.appointment_data['patient_type'] == 'new' else "Returning",
                "patient_data": {
                    "name": st.session_state.appointment_data['patient_name'],
                    "email": st.session_state.appointment_data['patient_email'],
                    "insurance_carrier": st.session_state.appointment_data.get('insurance_carrier', 'None'),
                    "insurance_member_id": st.session_state.appointment_data.get('insurance_member_id', ''),
                    "insurance_group": st.session_state.appointment_data.get('insurance_group_id', ''),
                },
                "details": {
                    "doctor": st.session_state.appointment_data['doctor_preference'],
                    "location": st.session_state.appointment_data['location'],
                    "duration": f"{st.session_state.appointment_data['appointment_duration']} minutes",
                },
            }
            
            email_result = st.session_state.agent.email_service.send_confirmation_email(appt_data)
            
            if email_result and email_result.get('success'):
                st.success("✅ Confirmation email sent successfully!")
            else:
                st.warning("⚠️ Email sending failed, but appointment is confirmed.")
            
            # Send SMS confirmation
            from backend.integrations.sms_service import SMSReminder, ReminderStage
            # Convert appointment_datetime string to datetime object
            appointment_datetime = datetime.fromisoformat(st.session_state.appointment_data['appointment_datetime'])
            
            reminder = SMSReminder(
                patient_phone=st.session_state.appointment_data['patient_phone'],
                patient_name=st.session_state.appointment_data['patient_name'],
                appointment_date=appointment_datetime,
                appointment_time=st.session_state.appointment_data['appointment_time'],
                doctor_name=st.session_state.appointment_data['doctor_preference'],
                stage=ReminderStage.FIRST,
                appointment_id=appointment_id
            )
            sms_result = st.session_state.agent.sms_service.send_reminder(reminder)
            
            if sms_result[0]:  # SMS service returns (success, message_id)
                st.success("✅ SMS confirmation sent successfully!")
            else:
                st.warning("⚠️ SMS sending failed, but appointment is confirmed.")
            
            st.session_state.current_step = 7
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error sending confirmation: {str(e)}")

def step7_schedule_reminders():
    """Step 7: Schedule reminders"""
    st.markdown("## ⏰ Scheduling Reminders")
    st.markdown("=" * 30)
    
    with st.spinner("Scheduling reminders..."):
        try:
            # Schedule 3-stage reminders
            appointment_data = {
                'appointment_id': st.session_state.appointment_data['appointment_id'],
                'patient_name': st.session_state.appointment_data['patient_name'],
                'patient_email': st.session_state.appointment_data['patient_email'],
                'patient_phone': st.session_state.appointment_data['patient_phone'],
                'doctor_name': st.session_state.appointment_data['doctor_preference'],
                'date': st.session_state.appointment_data['appointment_date'],
                'time': st.session_state.appointment_data['appointment_time'],
                'appointment_datetime': st.session_state.appointment_data['appointment_datetime'],
                'location': st.session_state.appointment_data['location'],
                'appointment_duration': st.session_state.appointment_data['appointment_duration']
            }
            
            st.session_state.agent.reminder_system.schedule_appointment_reminders(appointment_data)
            
            st.success("✅ 3-stage reminder system scheduled!")
            st.info("""
            📧 **Reminder 1:** Confirmation + Intake Forms (sent now)
            📋 **Reminder 2:** Forms & Attendance Check (1 day before)
            ✅ **Reminder 3:** Final Confirmation (2 hours before)
            """)
            
            st.warning("**Note:** Reply with 'Appointment - Cancel' via SMS or email to cancel.")
            
            st.session_state.current_step = 8
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error scheduling reminders: {str(e)}")

def step8_export_data():
    """Step 8: Export data"""
    st.markdown("## 📊 Export Data")
    st.markdown("=" * 30)
    
    with st.spinner("Exporting appointment data..."):
        try:
            st.session_state.agent.step8_export_data(st.session_state.appointment_data)
            st.success("✅ Appointment data exported successfully!")
            
            st.balloons()
            st.success("🎉 **Appointment scheduling completed successfully!**")
            st.info("Thank you for using our medical scheduling system!")
            
            # Reset for new appointment
            if st.button("Schedule Another Appointment", type="primary"):
                st.session_state.current_step = 1
                st.session_state.appointment_data = {}
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Export failed: {str(e)}")

def main():
    """Main Streamlit app"""
    st.set_page_config(
        page_title="Medical Scheduling System",
        page_icon="🏥",
        layout="wide"
    )
    
    # Initialize agent
    initialize_agent()
    
    # Sidebar with progress
    st.sidebar.title("📋 Progress")
    steps = [
        "1. Patient Info",
        "2. Patient Lookup", 
        "3. Scheduling",
        "4. Insurance",
        "5. Confirmation",
        "6. Send Confirmation",
        "7. Schedule Reminders",
        "8. Export Data"
    ]
    
    for i, step in enumerate(steps, 1):
        if i < st.session_state.current_step:
            st.sidebar.success(step)
        elif i == st.session_state.current_step:
            st.sidebar.info(step)
        else:
            st.sidebar.text(step)
    
    # Main content based on current step
    if st.session_state.current_step == 1:
        step1_greeting_and_collect_info()
    elif st.session_state.current_step == 2:
        step2_patient_lookup()
    elif st.session_state.current_step == 3:
        step3_smart_scheduling()
    elif st.session_state.current_step == 4:
        step4_insurance_collection()
    elif st.session_state.current_step == 5:
        step5_appointment_confirmation()
    elif st.session_state.current_step == 6:
        step6_send_confirmation()
    elif st.session_state.current_step == 7:
        step7_schedule_reminders()
    elif st.session_state.current_step == 8:
        step8_export_data()

if __name__ == "__main__":
    main()
