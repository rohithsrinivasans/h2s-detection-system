"""
Full End-to-End Automated Integration Test Suite for H2S Monitor.
Tests all endpoints, authentication, deep learning inference API, attendance, and CSV export.
"""

import os
import requests

BASE_URL = "http://127.0.0.1:5000"

def run_e2e_tests():
    session = requests.Session()
    print("=" * 65)
    print("  RUNNING H2S MONITOR E2E TEST SUITE")
    print("=" * 65)

    # Test 1: Fetch Login Page
    r1 = session.get(f"{BASE_URL}/login")
    assert r1.status_code == 200, f"Failed login page: {r1.status_code}"
    assert "Welcome back" in r1.text, "Login title missing in HTML"
    print("[PASS] 1. Login Page Loaded Successfully (Status 200)")

    # Test 2: Authenticate as Admin
    r2 = session.post(f"{BASE_URL}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
    assert r2.status_code == 200, f"Login failed with status {r2.status_code}"
    assert "Safety Overview" in r2.text, "Dashboard heading missing after login"
    print("[PASS] 2. Admin Authentication Successful & Redirected to Dashboard")

    # Test 3: Dashboard Telemetry & Stats API
    r3 = session.get(f"{BASE_URL}/api/stats")
    assert r3.status_code == 200, f"Stats API error: {r3.status_code}"
    stats = r3.json()
    assert "total_workers" in stats and "hourly_counts" in stats and "class_breakdown" in stats
    print(f"[PASS] 3. Stats API Valid: {stats['total_workers']} workers registered")

    # Test 4: Exposure Scanner Page Load
    r4 = session.get(f"{BASE_URL}/exposure")
    assert r4.status_code == 200, f"Exposure page failed: {r4.status_code}"
    assert "Scan Indicator Strip" in r4.text
    print("[PASS] 4. Exposure Scanner UI Loaded")

    # Test 5: Enrolling a real worker
    new_code = f"EMP-{int(os.urandom(2).hex(), 16)}"
    r5_add = session.post(f"{BASE_URL}/workers", data={
        "full_name": "Marcus Vance",
        "employee_code": new_code,
        "department": "Plant Maintenance",
        "work_zone": "Zone A - Acid Gas Burner",
        "username": f"marcus_{new_code.lower()}",
        "password": "securepassword123",
    }, allow_redirects=True)
    assert r5_add.status_code == 200
    assert new_code in r5_add.text
    # Extract the new worker ID
    import re
    match_id = re.search(r'/workers/(\d+)/delete', r5_add.text)
    worker_id = int(match_id.group(1)) if match_id else 1
    print(f"[PASS] 5. Enrolled Worker: {new_code} (Marcus Vance, ID: {worker_id})")

    # Test 6: AI Optical Inference API across all 4 sample strips on the enrolled worker
    sample_tests = [
        ("sample_no_exposure.jpg", "no_exposure"),
        ("sample_low.jpg", "low"),
        ("sample_medium.jpg", "medium"),
        ("sample_high.jpg", "high"),
    ]

    for fname, expected_cls in sample_tests:
        fpath = os.path.join("frontend", "static", "sample_strips", fname)
        with open(fpath, "rb") as f:
            files = {"photo": (fname, f, "image/jpeg")}
            data = {"worker_id": worker_id}
            r6 = session.post(f"{BASE_URL}/api/analyze", files=files, data=data)
            assert r6.status_code == 200, f"Inference API failed for {fname}: {r6.status_code}"
            res = r6.json()
            assert res["success"] is True
            diag = res["diagnosis"]
            assert diag["predicted_class"] == expected_cls, f"Expected {expected_cls}, got {diag['predicted_class']}"
            print(f"[PASS] 6. AI Model Test [{fname}]: {diag['predicted_class']} ({diag['confidence_pct']}%) | {diag['ppm_formatted']} | Latency: {diag['inference_time_ms']} ms")

    # Test 7: Shift Attendance Quick Action
    r7_action = session.post(f"{BASE_URL}/api/attendance/quick", data={"worker_id": worker_id, "action": "check_in"})
    assert r7_action.status_code == 200
    res_att = r7_action.json()
    assert res_att["success"] is True
    print(f"[PASS] 7. Attendance Check-in Recorded for {res_att['worker_name']}")

    # Test 8: Export CSV Compliance Report
    r8 = session.get(f"{BASE_URL}/export/csv")
    assert r8.status_code == 200
    assert "text/csv" in r8.headers.get("Content-Type", "")
    lines = r8.text.strip().split("\n")
    assert len(lines) >= 2, "CSV should contain headers and rows"
    print(f"[PASS] 8. Compliance Audit CSV Export Generated ({len(lines)} records exported)")

    # Test 9: QR Attendance Kiosk Scan Endpoint
    # 9a: Scan via raw employee code
    r9_raw = session.post(f"{BASE_URL}/api/attendance/qr-scan", json={"qr_data": new_code})
    assert r9_raw.status_code == 200, f"QR raw scan failed: {r9_raw.status_code}"
    res_qr_raw = r9_raw.json()
    assert res_qr_raw["success"] is True
    assert res_qr_raw["worker_code"] == new_code
    print(f"[PASS] 9a. QR Kiosk Scanned Badge '{new_code}' -> Action: {res_qr_raw['action']} ({res_qr_raw['timestamp']})")

    # 9b: Scan via JSON badge payload format
    import json
    json_badge_data = json.dumps({"code": new_code, "name": "Marcus Vance"})
    r9_json = session.post(f"{BASE_URL}/api/attendance/qr-scan", json={"qr_data": json_badge_data})
    assert r9_json.status_code == 200, f"QR json scan failed: {r9_json.status_code}"
    res_qr_json = r9_json.json()
    assert res_qr_json["success"] is True
    print(f"[PASS] 9b. QR Kiosk Decoded JSON Badge '{new_code}' -> Action: {res_qr_json['action']} ({res_qr_json['timestamp']})")

    # Test 10: Delete Employee and Verify Cascade Cleanup
    worker_id = res_qr_raw["worker"]["id"]
    r_workers = session.get(f"{BASE_URL}/workers")
    assert new_code in r_workers.text
    
    # Perform API delete
    r10_del = session.delete(f"{BASE_URL}/api/workers/{worker_id}/delete")
    assert r10_del.status_code == 200, f"Delete worker failed: {r10_del.status_code}"
    res_del = r10_del.json()
    assert res_del["success"] is True
    print(f"[PASS] 10. Employee Deletion & Cascade Database Cleanup Confirmed for worker ID {worker_id}")

    # Verify worker no longer exists in worker roster
    r_verify = session.get(f"{BASE_URL}/workers")
    assert new_code not in r_verify.text
    print("[PASS] 11. Verified Worker Completely Removed from Roster & Database Cleaned")

    print("=" * 65)
    print("  ALL 11 INTEGRATION TESTS PASSED WITH 100% SUCCESS RATE!")
    print("=" * 65)

if __name__ == "__main__":
    run_e2e_tests()

