import re
text = """PASTE OCR TEXT HERE"""

emails = re.findall(r"[a-zA-Z0-9._%%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
phones = re.findall(r"\b[6-9][0-9]{9}\b", text)
passwords = re.findall(r"[a-zA-Z0-9@#]{6,}", text)

print("Emails:", emails)
print("Phones:", phones)
print("Possible Passwords:", passwords)
