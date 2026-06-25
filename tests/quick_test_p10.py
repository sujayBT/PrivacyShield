import requests, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = 'http://localhost:8000/api'
requests.post(f'{BASE}/auth/register', json={'username':'admin','password':'admin'})
r = requests.post(f'{BASE}/auth/login',
    data={'username':'admin','password':'admin'},
    headers={'Content-Type':'application/x-www-form-urlencoded'})
tok = r.json()['access_token']
H = {'Authorization': f'Bearer {tok}'}

FILES = [
    ('test_photo_with_gps.jpg',   'image/jpeg'),
    ('test_document_author.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    ('test_spreadsheet.xlsx',     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
]
folder = r'C:\PrivacyExposureProject\test_files_phase10'
print()
all_ok = True
for fname, mime in FILES:
    fp = os.path.join(folder, fname)
    with open(fp, 'rb') as f:
        resp = requests.post(f'{BASE}/metadata/scan',
            files={'file': (fname, f, mime)}, headers=H, timeout=30)
    d = resp.json()
    ok = resp.status_code == 200
    if not ok:
        all_ok = False
    status = 'OK  ' if ok else 'FAIL'
    score  = d.get('score', '?')
    risk   = d.get('risk_level', '?')
    count  = d.get('finding_count', '?')
    print(f'[{status}] {fname}')
    print(f'       HTTP={resp.status_code}  score={score}  risk={risk}  findings={count}')
    if not ok:
        print(f'       ERROR: {resp.text[:300]}')
    else:
        # Show first 3 findings
        for f2 in d.get('findings', [])[:3]:
            print(f'       - {f2["field"]}: {str(f2["value"])[:60]}')
    print()

print('ALL 3 FILES PASSED - Backend is working!' if all_ok else 'SOME FAILED - check errors above')
print('Frontend: http://localhost:5173/metadata-scan')
print('Files folder: C:\\PrivacyExposureProject\\test_files_phase10\\')
