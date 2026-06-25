import pytesseract
from PIL import Image, ImageDraw, ImageFilter


def blur_sensitive_data(image_path, output_path="blurred_output.png"):
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # Get text with bounding boxes
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    sensitive_keywords = [
        "password", "login", "account",
        "bank", "otp", "email",
        "phone", "upi", "card"
    ]

    n_boxes = len(data['text'])

    for i in range(n_boxes):
        word = data['text'][i]

        for keyword in sensitive_keywords:
            if keyword.lower() in word.lower():

                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]

                # Crop region
                region = img.crop((x, y, x + w, y + h))

                # Apply blur
                blurred = region.filter(ImageFilter.GaussianBlur(10))

                # Paste back
                img.paste(blurred, (x, y))

    img.save(output_path)
    return output_path