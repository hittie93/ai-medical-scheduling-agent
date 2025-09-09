"""
Insurance Information Collection and Validation System
Handles insurance carrier, member ID, and group number collection
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re
import json
from datetime import datetime
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InsuranceCarrier(Enum):
    """Common insurance carriers"""
    AETNA = "Aetna"
    BLUECROSS = "Blue Cross Blue Shield"
    CIGNA = "Cigna"
    UNITED = "UnitedHealthcare"
    HUMANA = "Humana"
    KAISER = "Kaiser Permanente"
    ANTHEM = "Anthem"
    MEDICARE = "Medicare"
    MEDICAID = "Medicaid"
    TRICARE = "Tricare"
    OTHER = "Other"

class InsuranceVerificationStatus(Enum):
    """Insurance verification status"""
    VERIFIED = "verified"
    PENDING = "pending"
    INVALID = "invalid"
    EXPIRED = "expired"
    NOT_COVERED = "not_covered"

@dataclass
class InsuranceInfo:
    """Insurance information data structure"""
    carrier: str
    member_id: str
    group_number: Optional[str] = None
    policy_holder_name: Optional[str] = None
    policy_holder_dob: Optional[str] = None
    relationship_to_patient: Optional[str] = "self"
    verification_status: InsuranceVerificationStatus = InsuranceVerificationStatus.PENDING
    verification_date: Optional[datetime] = None
    copay_amount: Optional[float] = None
    deductible_met: Optional[float] = None
    coverage_details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['verification_status'] = self.verification_status.value
        data['verification_date'] = (
            self.verification_date.isoformat() 
            if self.verification_date else None
        )
        return data
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate insurance information
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Validate carrier
        if not self.carrier or len(self.carrier) < 3:
            errors.append("Insurance carrier name is required")
        
        # Validate member ID
        if not self.member_id or len(self.member_id) < 5:
            errors.append("Member ID must be at least 5 characters")
        
        # Validate relationship
        valid_relationships = ['self', 'spouse', 'child', 'parent', 'other']
        if self.relationship_to_patient not in valid_relationships:
            errors.append(f"Relationship must be one of: {', '.join(valid_relationships)}")
        
        # If not self, policy holder info required
        if self.relationship_to_patient != 'self':
            if not self.policy_holder_name:
                errors.append("Policy holder name required when patient is not the policy holder")
            if not self.policy_holder_dob:
                errors.append("Policy holder date of birth required when patient is not the policy holder")
        
        return len(errors) == 0, errors

class InsuranceValidator:
    """Validates and processes insurance information"""
    
    def __init__(self):
        self.carrier_patterns = self._load_carrier_patterns()
        self.insurance_db_path = Path("data/insurance_verifications.json")
        self.load_insurance_db()
    
    def _load_carrier_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load validation patterns for different insurance carriers"""
        return {
            InsuranceCarrier.AETNA.value: {
                'member_id_pattern': r'^[A-Z]\d{8}$',
                'group_required': True,
                'group_pattern': r'^\d{5,7}$'
            },
            InsuranceCarrier.BLUECROSS.value: {
                'member_id_pattern': r'^[A-Z]{3}\d{9}$',
                'group_required': True,
                'group_pattern': r'^[A-Z0-9]{5,10}$'
            },
            InsuranceCarrier.CIGNA.value: {
                'member_id_pattern': r'^\d{9}$',
                'group_required': True,
                'group_pattern': r'^\d{6,7}$'
            },
            InsuranceCarrier.UNITED.value: {
                'member_id_pattern': r'^\d{9,11}$',
                'group_required': False,
                'group_pattern': r'^[A-Z0-9]{5,10}$'
            },
            InsuranceCarrier.MEDICARE.value: {
                'member_id_pattern': r'^\d{3}-\d{2}-\d{4}[A-Z]?$',
                'group_required': False,
                'group_pattern': None
            },
            InsuranceCarrier.MEDICAID.value: {
                'member_id_pattern': r'^[A-Z0-9]{8,12}$',
                'group_required': False,
                'group_pattern': None
            }
        }
    
    def load_insurance_db(self):
        """Load insurance verification database"""
        if self.insurance_db_path.exists():
            try:
                with open(self.insurance_db_path, 'r') as f:
                    self.insurance_db = json.load(f)
                logger.info(f"Loaded {len(self.insurance_db)} insurance records")
            except Exception as e:
                logger.error(f"Error loading insurance database: {e}")
                self.insurance_db = {}
        else:
            self.insurance_db = {}
    
    def save_insurance_db(self):
        """Save insurance verification database"""
        try:
            self.insurance_db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.insurance_db_path, 'w') as f:
                json.dump(self.insurance_db, f, indent=2)
            logger.info(f"Saved {len(self.insurance_db)} insurance records")
        except Exception as e:
            logger.error(f"Error saving insurance database: {e}")
    
    def normalize_carrier_name(self, carrier_input: str) -> str:
        """
        Normalize carrier name to standard format
        
        Args:
            carrier_input: User input for carrier name
            
        Returns:
            Normalized carrier name
        """
        carrier_lower = carrier_input.lower().strip()
        
        # Common variations mapping
        carrier_mapping = {
            'aetna': InsuranceCarrier.AETNA.value,
            'blue cross': InsuranceCarrier.BLUECROSS.value,
            'bcbs': InsuranceCarrier.BLUECROSS.value,
            'blue shield': InsuranceCarrier.BLUECROSS.value,
            'cigna': InsuranceCarrier.CIGNA.value,
            'united': InsuranceCarrier.UNITED.value,
            'unitedhealthcare': InsuranceCarrier.UNITED.value,
            'uhc': InsuranceCarrier.UNITED.value,
            'humana': InsuranceCarrier.HUMANA.value,
            'kaiser': InsuranceCarrier.KAISER.value,
            'anthem': InsuranceCarrier.ANTHEM.value,
            'medicare': InsuranceCarrier.MEDICARE.value,
            'medicaid': InsuranceCarrier.MEDICAID.value,
            'tricare': InsuranceCarrier.TRICARE.value
        }
        
        for key, value in carrier_mapping.items():
            if key in carrier_lower:
                return value
        
        return carrier_input  # Return original if no match
    
    def validate_member_id(self, member_id: str, carrier: str) -> Tuple[bool, str]:
        """
        Validate member ID format for specific carrier
        
        Args:
            member_id: Member ID to validate
            carrier: Insurance carrier name
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Clean member ID
        clean_id = member_id.strip().upper()
        
        # Get validation pattern for carrier
        carrier_config = self.carrier_patterns.get(carrier)
        
        if not carrier_config:
            # Generic validation for unknown carriers
            if len(clean_id) < 5 or len(clean_id) > 20:
                return False, "Member ID should be between 5 and 20 characters"
            return True, ""
        
        # Validate against pattern
        pattern = carrier_config.get('member_id_pattern')
        if pattern:
            if not re.match(pattern, clean_id):
                return False, f"Invalid member ID format for {carrier}"
        
        return True, ""
    
    def validate_group_number(self, group_number: str, carrier: str) -> Tuple[bool, str]:
        """
        Validate group number format for specific carrier
        
        Args:
            group_number: Group number to validate
            carrier: Insurance carrier name
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        carrier_config = self.carrier_patterns.get(carrier)
        
        if not carrier_config:
            # Generic validation
            return True, ""
        
        # Check if group number is required
        if carrier_config.get('group_required') and not group_number:
            return False, f"Group number is required for {carrier}"
        
        # Validate against pattern if provided
        if group_number:
            clean_group = group_number.strip().upper()
            pattern = carrier_config.get('group_pattern')
            
            if pattern and not re.match(pattern, clean_group):
                return False, f"Invalid group number format for {carrier}"
        
        return True, ""
    
    def collect_insurance_info(self, user_inputs: Dict[str, Any]) -> InsuranceInfo:
        """
        Collect and validate insurance information from user inputs
        
        Args:
            user_inputs: Dictionary containing user-provided insurance data
            
        Returns:
            InsuranceInfo object
        """
        # Extract and normalize carrier
        carrier = self.normalize_carrier_name(
            user_inputs.get('carrier', '').strip()
        )
        
        # Extract member ID
        member_id = user_inputs.get('member_id', '').strip().upper()
        
        # Extract group number (optional)
        group_number = user_inputs.get('group_number', '').strip().upper() if user_inputs.get('group_number') else None
        
        # Create insurance info object
        insurance_info = InsuranceInfo(
            carrier=carrier,
            member_id=member_id,
            group_number=group_number,
            policy_holder_name=user_inputs.get('policy_holder_name'),
            policy_holder_dob=user_inputs.get('policy_holder_dob'),
            relationship_to_patient=user_inputs.get('relationship', 'self')
        )
        
        return insurance_info
    
    def verify_insurance(self, insurance_info: InsuranceInfo) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify insurance information (simulated for demo)
        
        Args:
            insurance_info: Insurance information to verify
            
        Returns:
            Tuple of (success, verification_details)
        """
        # Validate basic info
        is_valid, errors = insurance_info.validate()
        
        if not is_valid:
            return False, {'errors': errors, 'status': InsuranceVerificationStatus.INVALID}
        
        # Validate member ID format
        id_valid, id_error = self.validate_member_id(
            insurance_info.member_id, 
            insurance_info.carrier
        )
        
        if not id_valid:
            return False, {'errors': [id_error], 'status': InsuranceVerificationStatus.INVALID}
        
        # Validate group number if provided
        group_valid, group_error = self.validate_group_number(
            insurance_info.group_number,
            insurance_info.carrier
        )
        
        if not group_valid:
            return False, {'errors': [group_error], 'status': InsuranceVerificationStatus.INVALID}
        
        # Simulate verification (in production, this would call insurance API)
        verification_result = self._simulate_verification(insurance_info)
        
        # Update insurance info with verification results
        insurance_info.verification_status = verification_result['status']
        insurance_info.verification_date = datetime.now()
        insurance_info.copay_amount = verification_result.get('copay')
        insurance_info.deductible_met = verification_result.get('deductible_met')
        insurance_info.coverage_details = verification_result.get('coverage')
        
        # Store in database
        verification_id = f"{insurance_info.carrier}_{insurance_info.member_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.insurance_db[verification_id] = insurance_info.to_dict()
        self.save_insurance_db()
        
        return True, verification_result
    
    def _simulate_verification(self, insurance_info: InsuranceInfo) -> Dict[str, Any]:
        """
        Simulate insurance verification (for demo purposes)
        
        Args:
            insurance_info: Insurance information to verify
            
        Returns:
            Simulated verification result
        """
        # Simulate different scenarios based on carrier
        if insurance_info.carrier == InsuranceCarrier.MEDICARE.value:
            return {
                'status': InsuranceVerificationStatus.VERIFIED,
                'copay': 0,
                'deductible_met': 0,
                'coverage': {
                    'plan_type': 'Medicare Part B',
                    'coverage_percentage': 80,
                    'annual_deductible': 226,
                    'preventive_care': 'Covered 100%'
                }
            }
        elif insurance_info.carrier == InsuranceCarrier.BLUECROSS.value:
            return {
                'status': InsuranceVerificationStatus.VERIFIED,
                'copay': 30,
                'deductible_met': 500,
                'coverage': {
                    'plan_type': 'PPO',
                    'in_network_coverage': 90,
                    'out_network_coverage': 70,
                    'annual_deductible': 1000,
                    'family_deductible': 3000
                }
            }
        else:
            # Generic verification
            return {
                'status': InsuranceVerificationStatus.VERIFIED,
                'copay': 25,
                'deductible_met': 250,
                'coverage': {
                    'plan_type': 'HMO',
                    'coverage_percentage': 85,
                    'annual_deductible': 500
                }
            }
    
    def format_insurance_summary(self, insurance_info: InsuranceInfo) -> str:
        """
        Format insurance information for display
        
        Args:
            insurance_info: Insurance information to format
            
        Returns:
            Formatted string summary
        """
        summary = f"""
Insurance Information:
----------------------
Carrier: {insurance_info.carrier}
Member ID: {insurance_info.member_id}
Group Number: {insurance_info.group_number or 'N/A'}
Policy Holder: {insurance_info.policy_holder_name or 'Self'}
Verification Status: {insurance_info.verification_status.value.upper()}
"""
        
        if insurance_info.copay_amount is not None:
            summary += f"Copay: ${insurance_info.copay_amount:.2f}\n"
        
        if insurance_info.deductible_met is not None:
            summary += f"Deductible Met: ${insurance_info.deductible_met:.2f}\n"
        
        if insurance_info.coverage_details:
            summary += "\nCoverage Details:\n"
            for key, value in insurance_info.coverage_details.items():
                summary += f"  - {key.replace('_', ' ').title()}: {value}\n"
        
        return summary
    
    def get_carrier_requirements(self, carrier: str) -> Dict[str, Any]:
        """
        Get specific requirements for an insurance carrier
        
        Args:
            carrier: Insurance carrier name
            
        Returns:
            Dictionary of requirements
        """
        carrier_normalized = self.normalize_carrier_name(carrier)
        config = self.carrier_patterns.get(carrier_normalized, {})
        
        return {
            'carrier': carrier_normalized,
            'group_required': config.get('group_required', False),
            'member_id_format': config.get('member_id_pattern', 'No specific format'),
            'group_format': config.get('group_pattern', 'No specific format')
        }


# Example usage and testing
if __name__ == "__main__":
    # Initialize validator
    validator = InsuranceValidator()
    
    # Test insurance collection
    test_inputs = {
        'carrier': 'Blue Cross',
        'member_id': 'ABC123456789',
        'group_number': 'GRP12345',
        'relationship': 'self'
    }
    
    # Collect and validate
    insurance_info = validator.collect_insurance_info(test_inputs)
    print("Collected Insurance Info:")
    print(validator.format_insurance_summary(insurance_info))
    
    # Verify insurance
    success, verification = validator.verify_insurance(insurance_info)
    
    if success:
        print("\n✅ Insurance Verified Successfully!")
        # Ensure JSON-serializable output (convert Enums to values)
        verification_out = dict(verification)
        status_val = verification_out.get('status')
        if isinstance(status_val, Enum):
            verification_out['status'] = status_val.value
        print(f"Verification Details: {json.dumps(verification_out, indent=2)}")
    else:
        print("\n❌ Insurance Verification Failed:")
        print(f"Errors: {verification.get('errors')}")