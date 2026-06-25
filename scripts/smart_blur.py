import cv2
import pytesseract
import re


def blur_sensitive_data(image_path):
    img = cv2.imread(image_path)

    if img is None:
        raise Exception("Image not found")

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    sensitive_patterns = [
        r"\S+@\S+",                      # email
        r"\b[6-9][0-9]{9}\b",            # phone
        r"[a-zA-Z0-9@#]{6,}"             # password
    ]

    for i in range(len(data['text'])):
        word = data['text'][i].strip()

        if word == "":
            continue

        for pattern in sensitive_patterns:
            if re.search(pattern, word):   # 🔥 FIX: search instead of fullmatch

                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]

                roi = img[y:y+h, x:x+w]
                blurred = cv2.GaussianBlur(roi, (51, 51), 30)
                img[y:y+h, x:x+w] = blurred

    output_path = "smart_blurred.png"
    cv2.imwrite(output_path, img)

    return output_path