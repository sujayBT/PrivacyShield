import sys
import os
import re
import pytesseract
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QFileDialog, QVBoxLayout, QHBoxLayout, QFrame, QScrollArea
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from privacy_score import calculate_privacy_score
from image_classifier import is_sensitive_image

# ---------- TESSERACT ----------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------- POPPLER ----------
POPPLER_PATH = r"C:\poppler\poppler-25.12.0\Library\bin"


# ---------- TEXT EXTRACTION ----------
def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    if ext in [".png", ".jpg", ".jpeg"]:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)

    elif ext == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        if text.strip() == "":
            images = convert_from_path(file_path, poppler_path=POPPLER_PATH)
            for img in images:
                text += pytesseract.image_to_string(img)

    return text


# ---------- MAIN UI ----------
class PrivacyExposureApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Privacy Exposure Score Tool")
        self.showMaximized()
        self.setStyleSheet(self.get_styles())

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()

        # 🔷 SIDEBAR
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background-color:#161b22;")

        side_layout = QVBoxLayout()
        side_layout.addWidget(QLabel("🔐 Privacy Tool"))

        btn1 = QPushButton("Dashboard")
        btn2 = QPushButton("Scan File")

        side_layout.addWidget(btn1)
        side_layout.addWidget(btn2)
        side_layout.addStretch()

        sidebar.setLayout(side_layout)

        # 🔷 CONTENT
        content = QFrame()
        content_layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        title = QLabel("Privacy Exposure Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("title")

        self.upload_btn = QPushButton("Upload File (Image / PDF)")
        self.upload_btn.clicked.connect(self.load_file)

        # CARD
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout()

        self.email_label = QLabel("📧 Emails: 0")
        self.phone_label = QLabel("📱 Phones: 0")
        self.password_label = QLabel("🔐 Passwords: 0")

        card_layout.addWidget(self.email_label)
        card_layout.addWidget(self.phone_label)
        card_layout.addWidget(self.password_label)

        card.setLayout(card_layout)

        # TEXT OUTPUT
        self.text_output = QLabel("Extracted Text will appear here...")
        self.text_output.setWordWrap(True)
        self.text_output.setStyleSheet("background:#020617; padding:10px; border-radius:10px;")

        # SCORE
        self.score_label = QLabel("Score: -")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setObjectName("score")

        # RISK
        self.risk_label = QLabel("Risk Level: -")
        self.risk_label.setAlignment(Qt.AlignCenter)
        self.risk_label.setObjectName("risk")

        # ADD
        content_layout.addWidget(title)
        content_layout.addWidget(self.upload_btn)
        content_layout.addWidget(card)
        content_layout.addWidget(self.text_output)
        content_layout.addWidget(self.score_label)
        content_layout.addWidget(self.risk_label)

        content.setLayout(content_layout)
        scroll.setWidget(content)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(scroll)

        self.setLayout(main_layout)

    def get_styles(self):
        return """
        QWidget {
            background-color: #0a0f1c;
            color: #e6edf3;
            font-family: Segoe UI;
        }

        #title {
            font-size: 30px;
            font-weight: bold;
            margin: 20px;
        }

        QPushButton {
            background-color: #22c55e;
            color: white;
            padding: 12px;
            border-radius: 10px;
        }

        QPushButton:hover {
            background-color: #16a34a;
        }

        QFrame {
            background-color: #111827;
            border-radius: 15px;
            padding: 15px;
        }

        #score {
            font-size: 24px;
            font-weight: bold;
        }

        #risk {
            font-size: 20px;
            font-weight: bold;
        }
        """

    # 🔥 FIXED FUNCTION
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Supported Files (*.png *.jpg *.jpeg *.pdf)"
        )

        if not file_path:
            return

        # TEXT
        text = extract_text_from_file(file_path)
        self.text_output.setText(text[:500])

        # IMAGE CLASSIFIER
        if file_path.endswith((".png", ".jpg", ".jpeg")):
            is_sensitive, results = is_sensitive_image(file_path)
        else:
            is_sensitive = False
        results = []

        # 🔥 SHOW AI RESULT (ADD THIS)
        if is_sensitive:
            self.text_output.setText(
        self.text_output.text() + "\n\n⚠️ Sensitive Image Detected!\n" + ", ".join(results)
    )

        # DETECTION
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        phones = re.findall(r"\b[6-9][0-9]{9}\b", text)

        raw_passwords = re.findall(r"[a-zA-Z0-9@#]{6,}", text)

        passwords = []
        for pwd in raw_passwords:
            if re.search(r"[0-9@#]", pwd):
                passwords.append(pwd)

        passwords = list(set(passwords))

        # SCORE
        score, risk, _ = calculate_privacy_score(
            emails, phones, passwords, unsafe_image=is_sensitive
        )

        # UPDATE UI
        self.email_label.setText(f"📧 Emails: {len(emails)}")
        self.phone_label.setText(f"📱 Phones: {len(phones)}")
        self.password_label.setText(f"🔐 Passwords: {len(passwords)}")

        self.score_label.setText(f"Score: {score}")
        self.risk_label.setText(f"Risk Level: {risk}")

        if risk == "HIGH":
            self.risk_label.setStyleSheet("color: red;")
        elif risk == "MEDIUM":
            self.risk_label.setStyleSheet("color: orange;")
        else:
            self.risk_label.setStyleSheet("color: green;")


# ---------- RUN ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PrivacyExposureApp()
    window.show()
    sys.exit(app.exec_())