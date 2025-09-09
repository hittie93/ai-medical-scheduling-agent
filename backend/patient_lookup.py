# backend/patient_lookup.py
"""
Patient database management using patients.csv
Handles new vs returning patient detection
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


class PatientDatabase:
    def __init__(self, db_path: str = "data/patients.csv"):
        """Initialize patient database"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if self.db_path.exists():
            self.df = pd.read_csv(self.db_path)
        else:
            # Create empty DataFrame if file not found
            self.df = pd.DataFrame(columns=[
                "Name", "DOB", "Doctor", "Location", "Insurance",
                "Email", "Phone", "Visit_Count", "Status"
            ])
            self.save()

    def save(self):
        """Save DataFrame to CSV"""
        self.df.to_csv(self.db_path, index=False)

    def search_patient(
        self,
        name: Optional[str] = None,
        dob: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Optional[Dict]:
        """Search for patient in database"""
        if self.df.empty:
            return None

        # Match by Name + DOB
        if name and dob:
            matches = self.df[
                (self.df["Name"].str.lower() == name.lower()) &
                (self.df["DOB"] == dob)
            ]
            if not matches.empty:
                return matches.iloc[0].to_dict()

        # Match by email
        if email:
            matches = self.df[self.df["Email"].str.lower() == email.lower()]
            if not matches.empty:
                return matches.iloc[0].to_dict()

        # Match by phone (digits only)
        if phone:
            clean_phone = "".join(filter(str.isdigit, str(phone)))
            for _, row in self.df.iterrows():
                if row["Phone"]:
                    db_phone = "".join(filter(str.isdigit, str(row["Phone"])))
                    if clean_phone == db_phone:
                        return row.to_dict()

        return None

    def add_patient(self, patient_data: Dict) -> None:
        """Add new patient to database"""
        # Restrict doctor to allowed list
        allowed_doctors = {"Dr. Sharma", "Dr. Iyer", "Dr. Mehta", "Dr. Kapoor", "Dr. Reddy"}
        doctor = patient_data.get("doctor") or patient_data.get("doctor_preference") or "Not Assigned"
        if doctor not in allowed_doctors:
            # default assignment
            doctor = "Dr. Sharma"
        new_patient = {
            "Name": patient_data.get("name"),
            "DOB": patient_data.get("dob"),
            "Doctor": doctor,
            "Location": patient_data.get("location", "Not Assigned"),
            "Insurance": patient_data.get("insurance", "None"),
            "Email": patient_data.get("email", ""),
            "Phone": patient_data.get("phone", ""),
            "Visit_Count": 0,
            "Status": "new"
        }
        self.df = pd.concat([self.df, pd.DataFrame([new_patient])], ignore_index=True)
        self.save()

    def update_patient(self, name: str, dob: str, updates: Dict) -> bool:
        """Update patient record by Name + DOB"""
        mask = (self.df["Name"].str.lower() == name.lower()) & (self.df["DOB"] == dob)
        if not mask.any():
            return False

        idx = self.df[mask].index[0]
        for key, value in updates.items():
            if key in self.df.columns:
                self.df.at[idx, key] = value

        self.save()
        return True

    def increment_visit(self, name: str, dob: str) -> bool:
        """Increment visit count and set status to returning"""
        mask = (self.df["Name"].str.lower() == name.lower()) & (self.df["DOB"] == dob)
        if not mask.any():
            return False

        idx = self.df[mask].index[0]
        self.df.at[idx, "Visit_Count"] = int(self.df.at[idx, "Visit_Count"]) + 1
        self.df.at[idx, "Status"] = "returning"
        self.save()
        return True

    def get_visit_count(self, name: str, dob: str) -> int:
        """Get current visit count for a patient"""
        mask = (self.df["Name"].str.lower() == name.lower()) & (self.df["DOB"] == dob)
        if not mask.any():
            return 0
        
        idx = self.df[mask].index[0]
        return int(self.df.at[idx, "Visit_Count"])

    def get_statistics(self) -> Dict:
        """Get basic patient statistics"""
        return {
            "total_patients": len(self.df),
            "returning_patients": len(self.df[self.df["Status"] == "returning"]),
            "new_patients": len(self.df[self.df["Status"] == "new"]),
            "avg_visits": float(self.df["Visit_Count"].mean()) if not self.df.empty else 0.0,
            "doctors": self.df["Doctor"].value_counts().to_dict(),
            "insurances": self.df["Insurance"].value_counts().to_dict()
        }





