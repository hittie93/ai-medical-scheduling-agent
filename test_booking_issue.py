#!/usr/bin/env python3
"""
Test script to verify the calendar booking issue
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_booking_issue():
    """Test if booking slots are properly updated"""
    print("🧪 Testing Calendar Booking Issue")
    print("=" * 50)
    
    try:
        from backend.integrations.calendly_service import CalendlyService
        
        # Initialize Calendly service
        calendly = CalendlyService(use_mock=True)
        
        # Test 1: Get available slots for Dr. Iyer
        print("\n📅 Test 1: Getting available slots for Dr. Iyer...")
        slots_before = calendly.get_available_slots(
            doctor_id="dr_iyer",
            date_from=datetime.now(),
            date_to=datetime.now() + timedelta(days=7),
            duration_minutes=30
        )
        
        print(f"Found {len(slots_before)} available slots")
        if slots_before:
            first_slot = slots_before[0]
            print(f"First slot: {first_slot['datetime']} - {first_slot['doctor_name']}")
        
        # Test 2: Book the first slot
        if slots_before:
            print("\n📝 Test 2: Booking the first slot...")
            patient_info = {
                "name": "Test Patient",
                "email": "test@example.com",
                "insurance_carrier": "None",
                "doctor_name": "Dr. Iyer",
                "location": "Main Clinic",
                "appointment_type": "returning_patient"
            }
            
            result = calendly.book_slot(slots_before[0], patient_info)
            print(f"Booking result: {result}")
            
            # Test 3: Get available slots again
            print("\n📅 Test 3: Getting available slots again...")
            slots_after = calendly.get_available_slots(
                doctor_id="dr_iyer",
                date_from=datetime.now(),
                date_to=datetime.now() + timedelta(days=7),
                duration_minutes=30
            )
            
            print(f"Found {len(slots_after)} available slots after booking")
            
            # Check if the booked slot is still in the list
            booked_datetime = slots_before[0]['datetime']
            still_available = any(slot['datetime'] == booked_datetime for slot in slots_after)
            
            if still_available:
                print("❌ ISSUE CONFIRMED: Booked slot is still showing as available!")
            else:
                print("✅ SUCCESS: Booked slot is no longer available!")
        
        # Test 4: Check Excel file
        print("\n📊 Test 4: Checking Excel file...")
        excel_file = Path("data/appointments.xlsx")
        if excel_file.exists():
            import pandas as pd
            df = pd.read_excel(excel_file)
            print(f"Excel file has {len(df)} rows")
            if len(df) > 0:
                print("Sample rows:")
                print(df.head())
                
                # Check for booked slots
                booked_slots = df[df['available'] == False]
                print(f"\nBooked slots: {len(booked_slots)}")
                if len(booked_slots) > 0:
                    print(booked_slots[['doctor', 'date', 'time', 'patient_name', 'available']])
        else:
            print("Excel file does not exist")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_booking_issue()
