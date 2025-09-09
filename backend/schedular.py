"""
Smart Scheduling System for Medical Appointments
Implements business logic: 60 min for new patients, 30 min for returning patients
"""

import pandas as pd
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple
import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PatientType(Enum):
    """Patient classification for appointment duration"""
    NEW = "new"
    RETURNING = "returning"

class AppointmentStatus(Enum):
    """Appointment status tracking"""
    AVAILABLE = "available"
    BOOKED = "booked"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

@dataclass
class TimeSlot:
    """Represents a time slot for appointments"""
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: AppointmentStatus
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    appointment_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['start_time'] = self.start_time.isoformat()
        result['end_time'] = self.end_time.isoformat()
        result['status'] = self.status.value
        return result

@dataclass
class DoctorSchedule:
    """Doctor's availability and schedule"""
    doctor_id: str
    doctor_name: str
    specialization: str
    location: str
    working_days: List[str]  # ['Monday', 'Tuesday', etc.]
    working_hours: Dict[str, Tuple[time, time]]  # {'Monday': (time(9,0), time(17,0))}
    lunch_break: Tuple[time, time]  # (time(12,0), time(13,0))
    booked_slots: List[TimeSlot]

class Scheduler:
    """
    Core scheduling engine implementing business logic
    - 60 minutes for new patients
    - 30 minutes for returning patients
    """
    
    # Business rule constants
    NEW_PATIENT_DURATION = 60  # minutes
    RETURNING_PATIENT_DURATION = 30  # minutes
    BUFFER_TIME = 5  # minutes between appointments
    
    def __init__(self, schedule_file: Optional[str] = None):
        """
        Initialize scheduler with doctor schedules
        
        Args:
            schedule_file: Path to Excel file with doctor schedules
        """
        self.doctors: Dict[str, DoctorSchedule] = {}
        self.appointments: Dict[str, Dict] = {}
        self.schedule_file = schedule_file or "data/doctor_schedules.xlsx"
        
        # Load or create schedules
        if os.path.exists(self.schedule_file):
            self.load_schedules()
        else:
            self.create_sample_schedules()
    
    def determine_patient_type(self, patient_data: Dict) -> PatientType:
        """
        Determine if patient is new or returning
        
        Args:
            patient_data: Dictionary with patient information
            
        Returns:
            PatientType enum value
        """
        # Check if patient has previous appointments
        if patient_data.get('last_visit_date'):
            return PatientType.RETURNING
        
        # Check if patient ID exists in system
        if patient_data.get('patient_id') and patient_data.get('is_registered', False):
            return PatientType.RETURNING
        
        return PatientType.NEW
    
    def get_appointment_duration(self, patient_type: PatientType) -> int:
        """
        Get appointment duration based on patient type
        
        Args:
            patient_type: NEW or RETURNING patient
            
        Returns:
            Duration in minutes
        """
        if patient_type == PatientType.NEW:
            return self.NEW_PATIENT_DURATION
        return self.RETURNING_PATIENT_DURATION
    
    def find_available_slots(self, doctor_id: str, date: datetime, 
                           patient_type: PatientType,
                           num_slots: int = 5) -> List[TimeSlot]:
        """
        Find available time slots for a specific doctor and date
        
        Args:
            doctor_id: Doctor's ID
            date: Date to check availability
            patient_type: Type of patient (for duration calculation)
            num_slots: Maximum number of slots to return
            
        Returns:
            List of available TimeSlot objects
        """
        if doctor_id not in self.doctors:
            logger.error(f"Doctor {doctor_id} not found")
            return []
        
        doctor = self.doctors[doctor_id]
        duration = self.get_appointment_duration(patient_type)
        
        # Check if doctor works on this day
        day_name = date.strftime('%A')
        if day_name not in doctor.working_days:
            logger.info(f"Doctor {doctor_id} doesn't work on {day_name}")
            return []
        
        # Get working hours for the day
        start_hour, end_hour = doctor.working_hours.get(day_name, (time(9, 0), time(17, 0)))
        
        # Create datetime objects for the working day
        work_start = datetime.combine(date.date(), start_hour)
        work_end = datetime.combine(date.date(), end_hour)
        lunch_start = datetime.combine(date.date(), doctor.lunch_break[0])
        lunch_end = datetime.combine(date.date(), doctor.lunch_break[1])
        
        # Get all booked slots for this day
        booked_on_date = [
            slot for slot in doctor.booked_slots 
            if slot.start_time.date() == date.date()
        ]
        
        available_slots = []
        current_time = work_start
        
        while current_time < work_end and len(available_slots) < num_slots:
            slot_end = current_time + timedelta(minutes=duration)
            
            # Skip if slot extends beyond working hours
            if slot_end > work_end:
                break
            
            # Skip lunch break
            if (current_time < lunch_end and slot_end > lunch_start):
                current_time = lunch_end
                continue
            
            # Check if slot conflicts with booked appointments
            is_available = True
            for booked in booked_on_date:
                if (current_time < booked.end_time and slot_end > booked.start_time):
                    is_available = False
                    current_time = booked.end_time + timedelta(minutes=self.BUFFER_TIME)
                    break
            
            if is_available:
                # Check if slot is in the past
                if current_time > datetime.now():
                    available_slots.append(TimeSlot(
                        start_time=current_time,
                        end_time=slot_end,
                        duration_minutes=duration,
                        status=AppointmentStatus.AVAILABLE,
                        doctor_id=doctor_id
                    ))
                
                current_time = slot_end + timedelta(minutes=self.BUFFER_TIME)
            
        return available_slots
    
    def book_appointment(self, doctor_id: str, patient_id: str, 
                        patient_type: PatientType,
                        slot_start: datetime,
                        patient_data: Dict) -> Tuple[bool, str, Dict]:
        """
        Book an appointment slot
        
        Args:
            doctor_id: Doctor's ID
            patient_id: Patient's ID
            patient_type: NEW or RETURNING patient
            slot_start: Start time of the appointment
            patient_data: Additional patient information
            
        Returns:
            Tuple of (success, appointment_id or error message, appointment_details)
        """
        if doctor_id not in self.doctors:
            return False, "Doctor not found", {}
        
        doctor = self.doctors[doctor_id]
        duration = self.get_appointment_duration(patient_type)
        slot_end = slot_start + timedelta(minutes=duration)
        
        # Check if slot is available
        for booked in doctor.booked_slots:
            if (slot_start < booked.end_time and slot_end > booked.start_time):
                return False, "Slot is already booked", {}
        
        # Generate appointment ID
        appointment_id = f"APT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{patient_id[:4]}"
        
        # Create the appointment slot
        new_slot = TimeSlot(
            start_time=slot_start,
            end_time=slot_end,
            duration_minutes=duration,
            status=AppointmentStatus.BOOKED,
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=appointment_id
        )
        
        # Add to doctor's booked slots
        doctor.booked_slots.append(new_slot)
        
        # Store appointment details
        appointment_details = {
            'appointment_id': appointment_id,
            'patient_id': patient_id,
            'patient_name': patient_data.get('name', 'Unknown'),
            'patient_type': patient_type.value,
            'doctor_id': doctor_id,
            'doctor_name': doctor.doctor_name,
            'specialization': doctor.specialization,
            'location': doctor.location,
            'date': slot_start.date().isoformat(),
            'start_time': slot_start.time().strftime('%H:%M'),
            'end_time': slot_end.time().strftime('%H:%M'),
            'duration_minutes': duration,
            'status': AppointmentStatus.BOOKED.value,
            'booked_at': datetime.now().isoformat(),
            'insurance_carrier': patient_data.get('insurance_carrier'),
            'insurance_member_id': patient_data.get('insurance_member_id'),
            'insurance_group': patient_data.get('insurance_group')
        }
        
        self.appointments[appointment_id] = appointment_details
        
        logger.info(f"Appointment {appointment_id} booked successfully")
        return True, appointment_id, appointment_details
    
    def cancel_appointment(self, appointment_id: str, reason: str = "") -> Tuple[bool, str]:
        """
        Cancel an appointment
        
        Args:
            appointment_id: Appointment ID to cancel
            reason: Cancellation reason
            
        Returns:
            Tuple of (success, message)
        """
        if appointment_id not in self.appointments:
            return False, "Appointment not found"
        
        appointment = self.appointments[appointment_id]
        doctor_id = appointment['doctor_id']
        
        if doctor_id in self.doctors:
            doctor = self.doctors[doctor_id]
            # Remove from booked slots
            doctor.booked_slots = [
                slot for slot in doctor.booked_slots 
                if slot.appointment_id != appointment_id
            ]
        
        # Update appointment status
        appointment['status'] = AppointmentStatus.CANCELLED.value
        appointment['cancelled_at'] = datetime.now().isoformat()
        appointment['cancellation_reason'] = reason
        
        logger.info(f"Appointment {appointment_id} cancelled")
        return True, "Appointment cancelled successfully"
    
    def reschedule_appointment(self, appointment_id: str, 
                             new_slot_start: datetime) -> Tuple[bool, str, Dict]:
        """
        Reschedule an existing appointment
        
        Args:
            appointment_id: Appointment ID to reschedule
            new_slot_start: New appointment start time
            
        Returns:
            Tuple of (success, message, updated_appointment)
        """
        if appointment_id not in self.appointments:
            return False, "Appointment not found", {}
        
        appointment = self.appointments[appointment_id]
        
        # Cancel the old appointment
        self.cancel_appointment(appointment_id, "Rescheduled")
        
        # Book new appointment with same details
        patient_type = PatientType.NEW if appointment['patient_type'] == 'new' else PatientType.RETURNING
        
        success, new_id, new_details = self.book_appointment(
            doctor_id=appointment['doctor_id'],
            patient_id=appointment['patient_id'],
            patient_type=patient_type,
            slot_start=new_slot_start,
            patient_data={
                'name': appointment['patient_name'],
                'insurance_carrier': appointment.get('insurance_carrier'),
                'insurance_member_id': appointment.get('insurance_member_id'),
                'insurance_group': appointment.get('insurance_group')
            }
        )
        
        if success:
            new_details['rescheduled_from'] = appointment_id
            logger.info(f"Appointment {appointment_id} rescheduled to {new_id}")
        
        return success, new_id if success else "Failed to reschedule", new_details
    
    def get_doctor_schedule(self, doctor_id: str, date: datetime) -> Dict:
        """
        Get doctor's schedule for a specific date
        
        Args:
            doctor_id: Doctor's ID
            date: Date to retrieve schedule
            
        Returns:
            Dictionary with schedule information
        """
        if doctor_id not in self.doctors:
            return {}
        
        doctor = self.doctors[doctor_id]
        day_name = date.strftime('%A')
        
        # Get appointments for the day
        day_appointments = [
            slot for slot in doctor.booked_slots
            if slot.start_time.date() == date.date()
        ]
        
        # Sort by start time
        day_appointments.sort(key=lambda x: x.start_time)
        
        schedule = {
            'doctor_id': doctor_id,
            'doctor_name': doctor.doctor_name,
            'date': date.date().isoformat(),
            'day': day_name,
            'is_working_day': day_name in doctor.working_days,
            'working_hours': None,
            'appointments': [],
            'total_appointments': len(day_appointments),
            'available_slots': []
        }
        
        if schedule['is_working_day']:
            start_hour, end_hour = doctor.working_hours.get(day_name, (time(9, 0), time(17, 0)))
            schedule['working_hours'] = {
                'start': start_hour.strftime('%H:%M'),
                'end': end_hour.strftime('%H:%M'),
                'lunch_start': doctor.lunch_break[0].strftime('%H:%M'),
                'lunch_end': doctor.lunch_break[1].strftime('%H:%M')
            }
            
            # Add appointment details
            for slot in day_appointments:
                apt_id = slot.appointment_id
                if apt_id in self.appointments:
                    schedule['appointments'].append(self.appointments[apt_id])
            
            # Find available slots for both patient types
            for patient_type in [PatientType.NEW, PatientType.RETURNING]:
                available = self.find_available_slots(doctor_id, date, patient_type, 3)
                if available:
                    schedule['available_slots'].append({
                        'patient_type': patient_type.value,
                        'duration': self.get_appointment_duration(patient_type),
                        'slots': [slot.to_dict() for slot in available]
                    })
        
        return schedule
    
    def create_sample_schedules(self):
        """Create sample doctor schedules for testing (restricted to 5 doctors)"""
        sample_doctors = [
            {
                'doctor_id': 'dr_mehta',
                'doctor_name': 'Dr. Mehta',
                'specialization': 'Orthopedics',
                'location': 'Main Clinic - Ortho',
                'working_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
                'working_hours': {
                    'Monday': (time(9, 0), time(17, 0)),
                    'Tuesday': (time(9, 0), time(17, 0)),
                    'Wednesday': (time(9, 0), time(17, 0)),
                    'Thursday': (time(9, 0), time(17, 0)),
                    'Friday': (time(9, 0), time(15, 0))
                },
                'lunch_break': (time(12, 0), time(13, 0))
            },
            {
                'doctor_id': 'dr_reddy',
                'doctor_name': 'Dr. Reddy',
                'specialization': 'Pediatrics',
                'location': 'Children\'s Wing',
                'working_days': ['Monday', 'Wednesday', 'Friday'],
                'working_hours': {
                    'Monday': (time(8, 0), time(16, 0)),
                    'Wednesday': (time(8, 0), time(16, 0)),
                    'Friday': (time(8, 0), time(14, 0))
                },
                'lunch_break': (time(12, 30), time(13, 30))
            },
            {
                'doctor_id': 'dr_kapoor',
                'doctor_name': 'Dr. Kapoor',
                'specialization': 'Dermatology',
                'location': 'Skin Center',
                'working_days': ['Tuesday', 'Wednesday', 'Thursday', 'Friday'],
                'working_hours': {
                    'Tuesday': (time(10, 0), time(18, 0)),
                    'Wednesday': (time(10, 0), time(18, 0)),
                    'Thursday': (time(10, 0), time(18, 0)),
                    'Friday': (time(10, 0), time(16, 0))
                },
                'lunch_break': (time(13, 0), time(14, 0))
            },
            {
                'doctor_id': 'dr_sharma',
                'doctor_name': 'Dr. Sharma',
                'specialization': 'General Medicine',
                'location': 'Main Clinic - GM',
                'working_days': ['Monday', 'Tuesday', 'Thursday', 'Friday'],
                'working_hours': {
                    'Monday': (time(9, 0), time(17, 0)),
                    'Tuesday': (time(9, 0), time(17, 0)),
                    'Thursday': (time(9, 0), time(17, 0)),
                    'Friday': (time(9, 0), time(15, 0))
                },
                'lunch_break': (time(12, 0), time(13, 0))
            },
            {
                'doctor_id': 'dr_iyer',
                'doctor_name': 'Dr. Iyer',
                'specialization': 'Cardiology',
                'location': 'Heart Center',
                'working_days': ['Monday', 'Wednesday', 'Friday'],
                'working_hours': {
                    'Monday': (time(8, 0), time(16, 0)),
                    'Wednesday': (time(8, 0), time(16, 0)),
                    'Friday': (time(8, 0), time(14, 0))
                },
                'lunch_break': (time(12, 30), time(13, 30))
            }
        ]
        
        for doc_data in sample_doctors:
            doctor = DoctorSchedule(
                doctor_id=doc_data['doctor_id'],
                doctor_name=doc_data['doctor_name'],
                specialization=doc_data['specialization'],
                location=doc_data['location'],
                working_days=doc_data['working_days'],
                working_hours=doc_data['working_hours'],
                lunch_break=doc_data['lunch_break'],
                booked_slots=[]
            )
            self.doctors[doc_data['doctor_id']] = doctor
        
        logger.info(f"Created {len(sample_doctors)} sample doctor schedules")
    
    def load_schedules(self):
        """Load doctor schedules from Excel file"""
        try:
            df = pd.read_excel(self.schedule_file)
            
            for _, row in df.iterrows():
                # Parse working days
                working_days = row['working_days'].split(',') if isinstance(row['working_days'], str) else []
                
                # Parse working hours
                working_hours = {}
                if isinstance(row['working_hours'], str):
                    hours_data = json.loads(row['working_hours'])
                    for day, hours in hours_data.items():
                        start_time = datetime.strptime(hours['start'], '%H:%M').time()
                        end_time = datetime.strptime(hours['end'], '%H:%M').time()
                        working_hours[day] = (start_time, end_time)
                
                # Parse lunch break
                lunch_start = datetime.strptime(row['lunch_start'], '%H:%M').time()
                lunch_end = datetime.strptime(row['lunch_end'], '%H:%M').time()
                
                doctor = DoctorSchedule(
                    doctor_id=row['doctor_id'],
                    doctor_name=row['doctor_name'],
                    specialization=row['specialization'],
                    location=row['location'],
                    working_days=working_days,
                    working_hours=working_hours,
                    lunch_break=(lunch_start, lunch_end),
                    booked_slots=[]
                )
                
                self.doctors[row['doctor_id']] = doctor
            
            logger.info(f"Loaded {len(self.doctors)} doctor schedules from {self.schedule_file}")
            
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")
            self.create_sample_schedules()
    
    def save_schedules(self, filepath: Optional[str] = None):
        """
        Save current schedules to Excel file
        
        Args:
            filepath: Path to save the file (uses default if None)
        """
        filepath = filepath or self.schedule_file
        
        data = []
        for doctor_id, doctor in self.doctors.items():
            # Prepare working hours as JSON
            working_hours_json = {}
            for day, (start, end) in doctor.working_hours.items():
                working_hours_json[day] = {
                    'start': start.strftime('%H:%M'),
                    'end': end.strftime('%H:%M')
                }
            
            data.append({
                'doctor_id': doctor_id,
                'doctor_name': doctor.doctor_name,
                'specialization': doctor.specialization,
                'location': doctor.location,
                'working_days': ','.join(doctor.working_days),
                'working_hours': json.dumps(working_hours_json),
                'lunch_start': doctor.lunch_break[0].strftime('%H:%M'),
                'lunch_end': doctor.lunch_break[1].strftime('%H:%M'),
                'total_appointments': len(doctor.booked_slots)
            })
        
        df = pd.DataFrame(data)
        df.to_excel(filepath, index=False)
        logger.info(f"Saved {len(data)} doctor schedules to {filepath}")
    
    def export_appointments(self, filepath: str = "data/exports/appointments_log.xlsx"):
        """
        Export all appointments to Excel for admin review
        
        Args:
            filepath: Path to save the Excel file
        """
        if not self.appointments:
            logger.warning("No appointments to export")
            return
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Prepare data for export
        appointments_list = []
        for apt_id, apt_data in self.appointments.items():
            appointments_list.append(apt_data)
        
        # Create DataFrame
        df = pd.DataFrame(appointments_list)
        
        # Sort by date and time
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['start_time'])
        df = df.sort_values('datetime')
        df = df.drop('datetime', axis=1)
        
        # Create Excel writer with multiple sheets
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # All appointments
            df.to_excel(writer, sheet_name='All Appointments', index=False)
            
            # Confirmed appointments
            confirmed_df = df[df['status'] == AppointmentStatus.BOOKED.value]
            confirmed_df.to_excel(writer, sheet_name='Confirmed', index=False)
            
            # Cancelled appointments
            cancelled_df = df[df['status'] == AppointmentStatus.CANCELLED.value]
            cancelled_df.to_excel(writer, sheet_name='Cancelled', index=False)
            
            # Summary statistics
            summary_data = {
                'Metric': [
                    'Total Appointments',
                    'Confirmed Appointments',
                    'Cancelled Appointments',
                    'New Patients',
                    'Returning Patients',
                    'Average Duration (minutes)',
                    'Total Hours Scheduled'
                ],
                'Value': [
                    len(df),
                    len(confirmed_df),
                    len(cancelled_df),
                    len(df[df['patient_type'] == 'new']),
                    len(df[df['patient_type'] == 'returning']),
                    df['duration_minutes'].mean(),
                    df['duration_minutes'].sum() / 60
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Doctor-wise breakdown
            doctor_summary = df.groupby(['doctor_name', 'specialization']).agg({
                'appointment_id': 'count',
                'duration_minutes': 'sum',
                'patient_type': lambda x: (x == 'new').sum()
            }).rename(columns={
                'appointment_id': 'total_appointments',
                'duration_minutes': 'total_minutes',
                'patient_type': 'new_patients'
            })
            doctor_summary.to_excel(writer, sheet_name='Doctor Summary')
        
        logger.info(f"Exported {len(df)} appointments to {filepath}")
        return filepath
    
    def get_daily_summary(self, date: datetime) -> Dict:
        """
        Get summary of appointments for a specific date
        
        Args:
            date: Date to get summary for
            
        Returns:
            Dictionary with daily statistics
        """
        date_str = date.date().isoformat()
        
        daily_appointments = [
            apt for apt in self.appointments.values()
            if apt['date'] == date_str
        ]
        
        summary = {
            'date': date_str,
            'total_appointments': len(daily_appointments),
            'confirmed': sum(1 for apt in daily_appointments if apt['status'] == AppointmentStatus.BOOKED.value),
            'cancelled': sum(1 for apt in daily_appointments if apt['status'] == AppointmentStatus.CANCELLED.value),
            'new_patients': sum(1 for apt in daily_appointments if apt['patient_type'] == 'new'),
            'returning_patients': sum(1 for apt in daily_appointments if apt['patient_type'] == 'returning'),
            'total_hours': sum(apt['duration_minutes'] for apt in daily_appointments) / 60,
            'doctors_working': len(set(apt['doctor_id'] for apt in daily_appointments)),
            'appointments_by_doctor': {}
        }
        
        # Group by doctor
        for apt in daily_appointments:
            doctor_name = apt['doctor_name']
            if doctor_name not in summary['appointments_by_doctor']:
                summary['appointments_by_doctor'][doctor_name] = {
                    'count': 0,
                    'new_patients': 0,
                    'returning_patients': 0,
                    'total_minutes': 0
                }
            
            summary['appointments_by_doctor'][doctor_name]['count'] += 1
            summary['appointments_by_doctor'][doctor_name]['total_minutes'] += apt['duration_minutes']
            
            if apt['patient_type'] == 'new':
                summary['appointments_by_doctor'][doctor_name]['new_patients'] += 1
            else:
                summary['appointments_by_doctor'][doctor_name]['returning_patients'] += 1
        
        return summary
    
    def optimize_schedule(self, doctor_id: str, date: datetime) -> List[Dict]:
        """
        Optimize schedule by identifying gaps and suggesting improvements
        
        Args:
            doctor_id: Doctor's ID
            date: Date to optimize
            
        Returns:
            List of optimization suggestions
        """
        suggestions = []
        
        if doctor_id not in self.doctors:
            return suggestions
        
        doctor = self.doctors[doctor_id]
        day_name = date.strftime('%A')
        
        if day_name not in doctor.working_days:
            return suggestions
        
        # Get working hours
        start_hour, end_hour = doctor.working_hours[day_name]
        work_start = datetime.combine(date.date(), start_hour)
        work_end = datetime.combine(date.date(), end_hour)
        
        # Get booked slots for the day
        day_slots = sorted(
            [slot for slot in doctor.booked_slots if slot.start_time.date() == date.date()],
            key=lambda x: x.start_time
        )
        
        # Find gaps
        current_time = work_start
        for slot in day_slots:
            gap_minutes = (slot.start_time - current_time).total_seconds() / 60
            
            # Skip lunch break
            lunch_start = datetime.combine(date.date(), doctor.lunch_break[0])
            lunch_end = datetime.combine(date.date(), doctor.lunch_break[1])
            
            if current_time < lunch_end and slot.start_time > lunch_start:
                # Adjust for lunch break
                if current_time < lunch_start:
                    gap_minutes = (lunch_start - current_time).total_seconds() / 60
            
            if gap_minutes >= self.RETURNING_PATIENT_DURATION + self.BUFFER_TIME:
                suggestions.append({
                    'type': 'gap_found',
                    'start_time': current_time.strftime('%H:%M'),
                    'end_time': slot.start_time.strftime('%H:%M'),
                    'duration_minutes': int(gap_minutes),
                    'can_fit': 'returning_patient' if gap_minutes >= self.RETURNING_PATIENT_DURATION else None,
                    'can_fit_new': gap_minutes >= self.NEW_PATIENT_DURATION
                })
            
            current_time = slot.end_time + timedelta(minutes=self.BUFFER_TIME)
        
        # Check end of day gap
        if current_time < work_end:
            gap_minutes = (work_end - current_time).total_seconds() / 60
            if gap_minutes >= self.RETURNING_PATIENT_DURATION:
                suggestions.append({
                    'type': 'end_of_day_availability',
                    'start_time': current_time.strftime('%H:%M'),
                    'end_time': work_end.strftime('%H:%M'),
                    'duration_minutes': int(gap_minutes),
                    'slots_available': int(gap_minutes // (self.RETURNING_PATIENT_DURATION + self.BUFFER_TIME))
                })
        
        # Calculate utilization
        total_work_minutes = (work_end - work_start).total_seconds() / 60
        lunch_duration = (lunch_end - lunch_start).total_seconds() / 60
        available_minutes = total_work_minutes - lunch_duration
        
        booked_minutes = sum(slot.duration_minutes for slot in day_slots)
        utilization = (booked_minutes / available_minutes) * 100 if available_minutes > 0 else 0
        
        suggestions.append({
            'type': 'utilization_report',
            'utilization_percent': round(utilization, 2),
            'total_available_minutes': int(available_minutes),
            'total_booked_minutes': int(booked_minutes),
            'total_appointments': len(day_slots),
            'recommendation': 'Good utilization' if utilization > 75 else 'Room for more appointments'
        })
        
        return suggestions


# Example usage
if __name__ == "__main__":
    # Initialize scheduler
    scheduler = Scheduler()
    
    # Test patient type determination
    new_patient = {'name': 'John Doe', 'patient_id': None}
    returning_patient = {'name': 'Jane Smith', 'patient_id': 'P001', 'is_registered': True}
    
    print(f"New patient type: {scheduler.determine_patient_type(new_patient)}")
    print(f"Returning patient type: {scheduler.determine_patient_type(returning_patient)}")
    
    # Find available slots
    tomorrow = datetime.now() + timedelta(days=1)
    available = scheduler.find_available_slots('DOC001', tomorrow, PatientType.NEW, 5)
    print(f"\nAvailable slots for new patient: {len(available)}")
    for slot in available[:3]:
        print(f"  {slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}")
    
    # Book an appointment
    if available:
        success, apt_id, details = scheduler.book_appointment(
            doctor_id='DOC001',
            patient_id='P001',
            patient_type=PatientType.NEW,
            slot_start=available[0].start_time,
            patient_data={
                'name': 'John Doe',
                'insurance_carrier': 'BlueCross',
                'insurance_member_id': 'BC123456',
                'insurance_group': 'GRP001'
            }
        )
        print(f"\nAppointment booked: {success}, ID: {apt_id}")
    
    # Get daily summary
    summary = scheduler.get_daily_summary(tomorrow)
    print(f"\nDaily summary for {summary['date']}:")
    print(f"  Total appointments: {summary['total_appointments']}")
    print(f"  New patients: {summary['new_patients']}")
    
    # Export appointments
    export_path = scheduler.export_appointments()
    print(f"\nAppointments exported to: {export_path}")