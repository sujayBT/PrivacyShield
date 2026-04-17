import cv2
import pytesseract
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def blur_sensitive_data(image_path):
    img = cv2.imread(image_path)
    h, w, _ = img.shape

    # OCR with bounding boxes
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    for i in range(len(data["text"])):
        word = data["text"][i]
        conf = int(data["conf"][i])

        # detect sensitive patterns
        if conf > 60 and (
            any(char.isdigit() for char in word) or
            "@" in word or
            len(word) >= 6
        ):
            x = data["left"][i]
            y = data["top"][i]
            width = data["width"][i]
            height = data["height"][i]

            roi = img[y:y+height, x:x+width]

            # blur region
            roi = cv2.GaussianBlur(roi, (51, 51), 30)

            img[y:y+height, x:x+width] = roi

    output_path = "smart_blurred.png"
    cv2.imwrite(output_path, img)

    return output_path