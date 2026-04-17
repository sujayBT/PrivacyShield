import sys
import os
import re
import pytesseract
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
from smart_blur import blur_sensitive_data # pyright: ignore[reportMissingImports]

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QFrame, QTextEdit
)
from PyQt5.QtCore import Qt


# ---------- PATH ----------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\poppler-25.12.0\Library\bin"


# ---------- TEXT EXTRACTION ----------
def extract_text_from_file(file_path):
    text = ""
    try:
        ext = os.path.splitext(file_path)[1].lower()

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

    except Exception as e:
        text = f"Error: {str(e)}"

    return text


# ---------- FIXED SCORING ----------
def calculate_privacy_score(emails, phones, passwords):
    score = 0

    # controlled weights (balanced)
    score += min(len(emails) * 5, 20)
    score += min(len(phones) * 10, 30)
    score += min(len(passwords) * 25, 50)

    score = min(score, 100)

    # risk mapping
    if score <= 30:
        risk = "LOW"
    elif score <= 70:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    return score, risk


# ---------- UI ----------
class PrivacyExposureApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Privacy Exposure Tool")
        self.resize(1100, 700)

        self.dark_mode = True
        self.current_file = None

        self.setStyleSheet(self.dark_style())
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()

        # ---------- SIDEBAR ----------
        sidebar = QFrame()
        sidebar.setFixedWidth(220)

        side_layout = QVBoxLayout()

        title = QLabel("🔐 Privacy Tool")
        title.setStyleSheet("font-size:18px; font-weight:bold;")

        btn1 = QLabel("• Dashboard")
        btn2 = QLabel("• Scan File")

        self.theme_btn = QPushButton("🌙 Dark")
        self.theme_btn.clicked.connect(self.toggle_theme)

        side_layout.addWidget(title)
        side_layout.addSpacing(20)
        side_layout.addWidget(btn1)
        side_layout.addWidget(btn2)
        side_layout.addStretch()
        side_layout.addWidget(self.theme_btn)

        sidebar.setLayout(side_layout)

        # ---------- MAIN ----------
        content = QFrame()
        content_layout = QVBoxLayout()

        header = QLabel("Privacy Exposure Dashboard")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size:24px; font-weight:bold;")

        # BUTTONS
        btn_layout = QHBoxLayout()

        self.upload_btn = QPushButton("Upload File")
        self.upload_btn.clicked.connect(self.load_file)

        self.blur_btn = QPushButton("Blur Sensitive Data")
        self.blur_btn.clicked.connect(self.blur_image)

        btn_layout.addWidget(self.upload_btn)
        btn_layout.addWidget(self.blur_btn)

        # METRICS
        metrics_layout = QHBoxLayout()

        self.email_label = QLabel("Emails: 0")
        self.phone_label = QLabel("Phones: 0")
        self.password_label = QLabel("Passwords: 0")

        metrics_layout.addWidget(self.email_label)
        metrics_layout.addWidget(self.phone_label)
        metrics_layout.addWidget(self.password_label)

        # OUTPUT
        self.output = QTextEdit()
        self.output.setReadOnly(True)

        # SCORE
        self.score_label = QLabel("Score: -")
        self.score_label.setAlignment(Qt.AlignCenter)

        self.risk_label = QLabel("Risk Level: -")
        self.risk_label.setAlignment(Qt.AlignCenter)

        content_layout.addWidget(header)
        content_layout.addLayout(btn_layout)
        content_layout.addLayout(metrics_layout)
        content_layout.addWidget(self.output)
        content_layout.addWidget(self.score_label)
        content_layout.addWidget(self.risk_label)

        content.setLayout(content_layout)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(content)

        self.setLayout(main_layout)

    # ---------- LOAD ----------
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Files (*.png *.jpg *.jpeg *.pdf)"
        )

        if not file_path:
            return

        self.current_file = file_path

        text = extract_text_from_file(file_path)
        self.output.setText(text)

        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        phones = re.findall(r"\b[6-9][0-9]{9}\b", text)
        passwords = re.findall(r"[a-zA-Z0-9@#]{6,}", text)

        score, risk = calculate_privacy_score(emails, phones, passwords)

        self.email_label.setText(f"Emails: {len(emails)}")
        self.phone_label.setText(f"Phones: {len(phones)}")
        self.password_label.setText(f"Passwords: {len(passwords)}")

        self.score_label.setText(f"Score: {score}")
        self.risk_label.setText(f"Risk Level: {risk}")

    # ---------- BLUR FIX ----------
        # ---------- SMART BLUR ----------
    def blur_image(self):
        if not self.current_file:
            self.output.append("\n⚠ Upload file first")
            return

        if not self.current_file.endswith((".png", ".jpg", ".jpeg")):
            self.output.append("\n⚠ Only image supported")
            return

        try:
            output_path = blur_sensitive_data(self.current_file)

            self.output.append(f"\n🔥 Smart Blur Applied: {output_path}")

        except Exception as e:
            self.output.append(f"\n❌ Error: {str(e)}")

    # ---------- THEME ----------
    def toggle_theme(self):
        if self.dark_mode:
            self.setStyleSheet(self.light_style())
            self.theme_btn.setText("☀ Light")
        else:
            self.setStyleSheet(self.dark_style())
            self.theme_btn.setText("🌙 Dark")

        self.dark_mode = not self.dark_mode

    def dark_style(self):
        return """
        QWidget { background:#0d1117; color:white; }
        QPushButton { background:#238636; padding:10px; border-radius:8px; }
        QPushButton:hover { background:#2ea043; }
        QFrame { background:#161b22; border-radius:10px; padding:10px; }
        QTextEdit { background:#020617; border-radius:10px; padding:10px; }
        """

    def light_style(self):
        return """
        QWidget { background:white; color:black; }
        QPushButton { background:#4CAF50; padding:10px; border-radius:8px; }
        QPushButton:hover { background:#45a049; }
        QFrame { background:#f0f0f0; border-radius:10px; padding:10px; }
        QTextEdit { background:#ffffff; border-radius:10px; padding:10px; }
        """


# ---------- RUN ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PrivacyExposureApp()
    window.show()
    sys.exit(app.exec_())