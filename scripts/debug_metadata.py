"""
Full Phase 10 end-to-end test — all 3 files, with full error detail
"""
import sys, os, requests
sys.path.insert(0, r"C:\PrivacyExposureProject")

BASE = "http://localhost:8000/api"

def login():
    creds = {"username": "admin", "password": "admin"}
    requests.post(f"{BASE}/auth/register", json=creds)
    r = requests.post(f"{BASE}/auth/login", data=creds,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    tok = r.json().get("access_token")
    print(f"Token: {tok[:30]}..." if tok else "NO TOKEN!")
    return tok

tok = login()
headers = {"Authorization": f"Bearer {tok}"}

FILES = [
    ("test_photo_with_gps.jpg",    "image/jpeg"),
    ("test_document_author.docx",  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("test_spreadsheet.xlsx",      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
]

folder = r"C:\PrivacyExposureProject\test_files_phase10"
print()

for fname, mime in FILES:
    fpath = os.path.join(folder, fname)
    if not os.path.exists(fpath):
        print(f"[MISSING] {fpath}")
        continue
    print(f"Testing: {fname}")
    with open(fpath, 'rb') as f:
        r = requests.post(f"{BASE}/metadata/scan",
            files={"file": (fname, f, mime)},
            headers=headers, timeout=30)
    print(f"  HTTP   : {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"  score  : {d['score']}")
        print(f"  risk   : {d['risk_level']}")
        print(f"  fields : {d['finding_count']} findings")
        print(f"  scan_id: {d['scan_id']}")
        print(f"  STATUS : ✅ OK")
    else:
        print(f"  ERROR  : {r.text[:500]}")
        print(f"  STATUS : ❌ FAIL")
    print()

# History
print("History:")
r = requests.get(f"{BASE}/metadata/history", headers=headers)
print(f"  HTTP: {r.status_code}, records: {len(r.json())}")
for s in r.json()[:5]:
    print(f"  #{s['scan_id']} [{s['file_type']:<6}] score={s['score']} {s['filename']}")

print(f"\nFrontend URL: http://localhost:5173/metadata-scan")
print("If you see 'Scan failed' in the UI, open browser DevTools > Console tab and copy the error.")
