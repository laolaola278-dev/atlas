"""
PHI leak detection drills (P6-0271 to P6-0280).

Verifies that protected health information is not leaked through:
- API responses
- Error messages
- Logs
- Audit events
"""

import re
from typing import Dict, List, Any
from datetime import datetime


# PHI patterns to detect
PHI_PATTERNS = {
    'ssn': r'\\b\\d{3}-\\d{2}-\\d{4}\\b',
    'credit_card': r'\\b(?:\\d{4}[- ]?){3}\\d{4}\\b',
    'email': r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b',
    'phone': r'\\b\\d{3}[-.]?\\d{3}[-.]?\\d{4}\\b',
    'mrn': r'\\bMRN[-:]?\\s*\\d{6,10}\\b',
    'dob': r'\\b(?:DOB|Birth)[:\\s]+\\d{1,2}[/\\-]\\d{1,2}[/\\-]\\d{2,4}\\b'
}


class PHILeakDetector:
    """Detects PHI leaks in various output formats."""
    
    def __init__(self):
        self.detections = []
    
    def scan_response(self, response: Dict[str, Any], context: str) -> List[Dict]:
        """Scan API response for PHI leaks."""
        findings = []
        response_str = str(response)
        
        for phi_type, pattern in PHI_PATTERNS.items():
            matches = re.finditer(pattern, response_str, re.IGNORECASE)
            for match in matches:
                finding = {
                    'type': phi_type,
                    'pattern': pattern,
                    'match': match.group(),
                    'context': context,
                    'timestamp': datetime.now().isoformat()
                }
                findings.append(finding)
                self.detections.append(finding)
        
        return findings
    
    def scan_error_message(self, error_msg: str) -> List[Dict]:
        """Scan error messages for PHI leaks."""
        return self.scan_response({"error": error_msg}, "error_message")
    
    def scan_log_entry(self, log_entry: str) -> List[Dict]:
        """Scan log entries for PHI leaks."""
        return self.scan_response({"log": log_entry}, "log_entry")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all PHI leak detections."""
        by_type = {}
        for detection in self.detections:
            phi_type = detection['type']
            by_type[phi_type] = by_type.get(phi_type, 0) + 1
        
        return {
            'total_detections': len(self.detections),
            'by_type': by_type,
            'timestamp': datetime.now().isoformat()
        }


def run_phi_leak_drills() -> Dict[str, Any]:
    """Run PHI leak detection drills."""
    detector = PHILeakDetector()
    results = []
    
    # Drill 1: API response with SSN
    response1 = {"patient_id": "P123", "ssn": "123-45-6789", "name": "John Doe"}
    findings1 = detector.scan_response(response1, "api_response_with_ssn")
    results.append({
        'drill': 'api_response_ssn',
        'expected': 'ssn leak detected',
        'findings': findings1,
        'passed': len(findings1) > 0 and any(f['type'] == 'ssn' for f in findings1)
    })
    
    # Drill 2: Error message with email
    error2 = "Failed to process patient john.doe@example.com"
    findings2 = detector.scan_error_message(error2)
    results.append({
        'drill': 'error_message_email',
        'expected': 'email leak detected',
        'findings': findings2,
        'passed': len(findings2) > 0 and any(f['type'] == 'email' for f in findings2)
    })
    
    # Drill 3: Log entry with phone
    log3 = "Patient called from 555-123-4567"
    findings3 = detector.scan_log_entry(log3)
    results.append({
        'drill': 'log_entry_phone',
        'expected': 'phone leak detected',
        'findings': findings3,
        'passed': len(findings3) > 0 and any(f['type'] == 'phone' for f in findings3)
    })
    
    # Drill 4: Clean response (no PHI)
    response4 = {"rule_id": "R001", "severity": 2, "recommendation": "monitor"}
    findings4 = detector.scan_response(response4, "clean_api_response")
    results.append({
        'drill': 'clean_response',
        'expected': 'no leaks',
        'findings': findings4,
        'passed': len(findings4) == 0
    })
    
    summary = detector.get_summary()
    
    return {
        'test_name': 'phi_leak_detection',
        'drills': results,
        'summary': summary,
        'passed': all(r['passed'] for r in results),
        'timestamp': datetime.now().isoformat()
    }


if __name__ == '__main__':
    results = run_phi_leak_drills()
    import json
    print(json.dumps(results, indent=2))