import zipfile, os

SRC = r'C:\Users\sujay\Downloads\CloudShield.odt'
DST = r'C:\Users\sujay\Downloads\PrivacyExposureScoreTool_Synopsis.odt'
TMP = DST + '.tmp'

# Get our modified content.xml from the dirty DST
with zipfile.ZipFile(DST, 'r') as z:
    raw = None
    for item in z.infolist():
        if item.filename == 'content.xml':
            raw = z.read(item)  # last one wins = our version
    new_content = raw

# Repack cleanly from original
with zipfile.ZipFile(SRC, 'r') as src_zip:
    with zipfile.ZipFile(TMP, 'w', compression=zipfile.ZIP_DEFLATED) as out_zip:
        for item in src_zip.infolist():
            if item.filename == 'content.xml':
                out_zip.writestr(item, new_content)
            else:
                out_zip.writestr(item, src_zip.read(item.filename))

os.replace(TMP, DST)
print('Repacked cleanly.')
print('Size:', os.path.getsize(DST), 'bytes')

with zipfile.ZipFile(DST, 'r') as z:
    c = z.read('content.xml').decode('utf-8')
    hits = {
        'Privacy Exposure Score Tool': 'Privacy Exposure Score Tool' in c,
        'Sujay .S. Bhat': 'Sujay .S. Bhat' in c,
        'P02ME24S126016': 'P02ME24S126016' in c,
        'CloudShield count': c.count('CloudShield'),
        'spaCy': 'spaCy' in c,
        'OpenCV': 'OpenCV' in c,
        'content.xml count': z.namelist().count('content.xml'),
    }
    for k, v in hits.items():
        print(f'  {k}: {v}')
