import re
import pytesseract
from PIL import Image
from privacy_score import calculate_privacy_score

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Load image
img = Image.open("sample.png")

# OCR extraction
text = pytesseract.image_to_string(img)

print("===== OCR TEXT =====")
print(text)

# Detect emails
emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)

# Detect phone numbers
phones = re.findall(r"\b[6-9][0-9]{9}\b", text)

# ---------- PASSWORD REFINEMENT START ----------

# Raw password-like matches
raw_passwords = re.findall(r"[a-zA-Z0-9@#]{6,}", text)

# Common words to ignore (platform independent)
ignore_words = [
    "password", "account", "security", "change",
    "english", "create", "strong",
    "facebook", "instagram", "whatsapp",
    "telegram", "twitter", "gmail"
]

passwords = []

for pwd in raw_passwords:
    pwd_lower = pwd.lower()

    # Ignore common words
    if pwd_lower in ignore_words:
        continue

    # Accept only if contains number or special symbol
    if re.search(r"[0-9@#]", pwd):
        passwords.append(pwd)

# Keep unique passwords only
passwords = list(set(passwords))

# ---------- PASSWORD REFINEMENT END ----------

print("\n===== DETECTED SENSITIVE DATA =====")
print("Emails:", emails)
print("Phones:", phones)
print("Passwords:", passwords)

# Calculate Privacy Exposure Score
score, risk, reasons = calculate_privacy_score(
    emails=emails,
    phones=phones,
    passwords=passwords,
    unsafe_image=False   # placeholder
)

print("\n===== PRIVACY EXPOSURE RESULT =====")
print("Score:", score)
print("Risk Level:", risk)
print("Reasons:", reasons)
