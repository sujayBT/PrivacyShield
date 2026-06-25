import cv2
import pytesseract
import re

def blur_image(image_path: str, output_path: str, finding_values: list[str] = None, face_boxes: list[list[int]] = None):
    img = cv2.imread(image_path)
    if img is None:
        raise Exception("Image not found")

    # ── 1. Blur Face Bounding Boxes ─────────────────────────────────────────
    if face_boxes:
        for box in face_boxes:
            if len(box) == 4:
                x, y, w, h = box
                # Add padding to face bounding boxes for safe margin
                padding = 8
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(img.shape[1] - x, w + 2 * padding)
                h = min(img.shape[0] - y, h + 2 * padding)

                roi = img[y:y+h, x:x+w]
                if roi.size != 0:
                    # Apply solid Gaussian blur to the face region
                    blurred = cv2.GaussianBlur(roi, (51, 51), 30)
                    img[y:y+h, x:x+w] = blurred

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    # Compile a set of normalized words from the detected findings
    words_to_blur = set()
    finding_substrings = []
    if finding_values:
        for val in finding_values:
            val_clean = val.strip().lower()
            if not val_clean:
                continue
            finding_substrings.append(val_clean)
            # Add individual words of length >= 3
            for word in re.split(r'[^a-zA-Z0-9@#$!%^&*_\-]', val_clean):
                if len(word) >= 3:
                    words_to_blur.add(word)

    # General fallback regex patterns for structured PII
    structured_patterns = [
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),  # Email
        re.compile(r"\b[6-9][0-9]{9}\b"),                                    # Phone
        re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b"),                        # Aadhaar
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                            # PAN card
        re.compile(r"\b(?:\d[ -]?){15,16}\b"),                               # Credit card
    ]

    for i in range(len(data['text'])):
        word = data['text'][i].strip()
        if not word or len(word) < 2:
            continue

        word_low = word.lower()
        should_blur = False

        # 1. Match against exact words in findings
        if word_low in words_to_blur:
            should_blur = True

        # 2. Check if the word is a substring of any full finding value
        # E.g. finding is "sujay8277#" and word is "sujay8277"
        if not should_blur:
            for sub in finding_substrings:
                if word_low in sub or sub in word_low:
                    # Avoid blurring short generic words by checking length
                    if len(word_low) >= 3:
                        should_blur = True
                        break

        # 3. Match against structured high-confidence regex patterns
        if not should_blur:
            for pattern in structured_patterns:
                if pattern.search(word):
                    should_blur = True
                    break

        if should_blur:
            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]

            # Add padding to the bounding box for a cleaner look and complete coverage
            padding = 4
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(img.shape[1] - x, w + 2 * padding)
            h = min(img.shape[0] - y, h + 2 * padding)

            roi = img[y:y+h, x:x+w]
            if roi.size != 0:
                # Strong Gaussian blur for solid protection
                blurred = cv2.GaussianBlur(roi, (51, 51), 30)
                img[y:y+h, x:x+w] = blurred

    cv2.imwrite(output_path, img)
    return output_path

