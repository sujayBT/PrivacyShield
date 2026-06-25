import pytesseract
from PIL import Image

def is_sensitive_image(img_path):
    try:
        img = Image.open(img_path)

        text = pytesseract.image_to_string(img)

        sensitive_keywords = [
            "password", "login", "account",
            "bank", "otp", "email",
            "phone", "upi", "card",
            "username", "security"
        ]

        detected = []

        for keyword in sensitive_keywords:
            if keyword.lower() in text.lower():
                detected.append(keyword)

        # 🔥 IMPORTANT FIX
        if detected:
            return True, detected
        else:
            return False, detected   # <- FIX HERE

    except:
        return False, []