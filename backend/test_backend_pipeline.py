import httpx
import json
import time

BASE_URL = "http://127.0.0.1:8001"

def print_result(title, data):
    print(f"\n{'='*50}\n{title}\n{'='*50}")
    if not data:
        print("No data or error occurred.")
        return
    
    if "status" in data:  # Health endpoint
        print(json.dumps(data, indent=2))
        return

    print(f"overall_risk_score: {data.get('overall_risk_score')}")
    print(f"risk_score_numeric: {data.get('risk_score_numeric')}")
    
    flags = data.get('flagged_clauses', [])
    print(f"number of flagged clauses: {len(flags)}")
    
    critical_count = sum(1 for c in flags if c.get('severity') == 'CRITICAL')
    print(f"critical flag count: {critical_count}")
    
    print("\nprocessing_metadata:")
    print(json.dumps(data.get('processing_metadata', {}), indent=2))
    
    print("\nflagged clause types:")
    for i, c in enumerate(flags, 1):
        print(f"  {i}. {c.get('type')} ({c.get('severity')}) - {c.get('confidence', 0)*100:.1f}%")
        
    print("\nFull JSON summary:")
    # We strip out the giant texts for a cleaner summary if desired, or print full
    summary = {
        "overall_risk_score": data.get("overall_risk_score"),
        "risk_score_numeric": data.get("risk_score_numeric"),
        "processing_metadata": data.get("processing_metadata"),
        "flagged_clauses": [{"type": c["type"], "severity": c["severity"]} for c in flags]
    }
    print(json.dumps(summary, indent=2))


def test_health():
    print("\nTesting GET /health...")
    try:
        r = httpx.get(f"{BASE_URL}/health")
        print(f"Status Code: {r.status_code}")
        print_result("GET /health", r.json())
    except Exception as e:
        print(f"Error: {e}")

def test_mock():
    print("\nTesting POST /api/analyze/mock...")
    try:
        r = httpx.post(f"{BASE_URL}/api/analyze/mock")
        print(f"Status Code: {r.status_code}")
        print_result("POST /api/analyze/mock", r.json())
    except Exception as e:
        print(f"Error: {e}")

def test_real(filename, title):
    print(f"\nTesting POST /api/analyze with {filename}...")
    try:
        with open(filename, 'rb') as f:
            r = httpx.post(
                f"{BASE_URL}/api/analyze",
                files={'file': f},
                data={'user_id': 'test_user'},
                timeout=30.0
            )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print_result(title, r.json())
        else:
            print(f"Error response: {r.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # test_health()
    # test_mock()
    test_real("clarity_high_risk_consent_sample.pdf", "POST /api/analyze (High Risk)")
    test_real("clarity_low_risk_consent_sample.pdf", "POST /api/analyze (Low Risk)")
