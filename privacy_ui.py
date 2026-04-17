import sys
import os
import re
import pytesseract
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
from smart_blur import blur_sensitive_data
from report_generator import generate_report

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QFrame, QTextEdit, QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap


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

    except Exception as e:
        text = f"Error: {str(e)}"

    return text


# ---------- SCORING ----------
def calculate_privacy_score(emails, phones, passwords):
    email_score = min(len(emails) * 10, 30)
    phone_score = min(len(phones) * 15, 30)
    password_score = min(len(passwords) * 30, 60)

    score = min(email_score + phone_score + password_score, 100)

    if score <= 30:
        risk = "LOW"
    elif score <= 70:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    return score, risk


# ---------- CLEAN IMAGE VIEWER ----------
class ImageViewer(QDialog):
    def __init__(self, image_path):
        super().__init__()

        self.setWindowTitle("Image Preview")

        # 👇 NORMAL WINDOW (NOT FULLSCREEN)
        self.resize(600, 800)

        self.setStyleSheet("background-color: #0d1117;")

        layout = QVBoxLayout()

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)

        self.pixmap = QPixmap(image_path)

        self.update_image()

        layout.addWidget(self.label)
        self.setLayout(layout)

    def update_image(self):
        if not self.pixmap.isNull():
            self.label.setPixmap(
                self.pixmap.scaled(
                    self.width()-40,
                    self.height()-40,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

    def resizeEvent(self, event):
        self.update_image()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


# ---------- UI ----------
class PrivacyExposureApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Privacy Exposure Tool")
        self.resize(1200, 750)

        self.current_file = None
        self.blurred_path = None

        self.setStyleSheet(self.dark_style())
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()

        # SIDEBAR
        sidebar = QFrame()
        sidebar.setFixedWidth(250)

        side_layout = QVBoxLayout()

        title = QLabel("🔐 Privacy Tool")
        title.setStyleSheet("font-size:20px; font-weight:bold; color:#58a6ff;")

        side_layout.addWidget(title)
        side_layout.addSpacing(20)
        side_layout.addWidget(QLabel("• Dashboard"))
        side_layout.addWidget(QLabel("• Scan File"))
        side_layout.addStretch()

        sidebar.setLayout(side_layout)

        # MAIN
        content = QFrame()
        content_layout = QVBoxLayout()

        header = QLabel("Privacy Exposure Dashboard")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size:26px; font-weight:bold;")

        btn_layout = QHBoxLayout()

        self.upload_btn = QPushButton("Upload Scan")
        self.upload_btn.clicked.connect(self.load_file)

        self.blur_btn = QPushButton("Blur Image")
        self.blur_btn.clicked.connect(self.blur_image)

        self.report_btn = QPushButton("Generate Report")
        self.report_btn.clicked.connect(self.generate_report_ui)

        btn_layout.addWidget(self.upload_btn)
        btn_layout.addWidget(self.blur_btn)
        btn_layout.addWidget(self.report_btn)

        metrics_layout = QHBoxLayout()

        self.email_label = QLabel("Emails: 0")
        self.phone_label = QLabel("Phones: 0")
        self.password_label = QLabel("Passwords: 0")

        metrics_layout.addWidget(self.email_label)
        metrics_layout.addWidget(self.phone_label)
        metrics_layout.addWidget(self.password_label)

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        # PREVIEW
        self.image_preview = QLabel("Click image to zoom")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setFixedHeight(300)
        self.image_preview.mousePressEvent = self.open_full_image

        self.score_label = QLabel("Score: -")
        self.score_label.setAlignment(Qt.AlignCenter)

        self.risk_label = QLabel("Risk Level: -")
        self.risk_label.setAlignment(Qt.AlignCenter)

        content_layout.addWidget(header)
        content_layout.addLayout(btn_layout)
        content_layout.addLayout(metrics_layout)
        content_layout.addWidget(self.output)
        content_layout.addWidget(self.image_preview)
        content_layout.addWidget(self.score_label)
        content_layout.addWidget(self.risk_label)

        content.setLayout(content_layout)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(content)

        self.setLayout(main_layout)

    # LOAD FILE
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "Files (*.png *.jpg *.jpeg *.pdf)"
        )

        if not file_path:
            return

        self.current_file = file_path

        text = extract_text_from_file(file_path)
        self.output.setText(text)

        emails = re.findall(r"\S+@\S+", text)
        phones = re.findall(r"\b[6-9][0-9]{9}\b", text)
        passwords = re.findall(r"[a-zA-Z0-9@#]{6,}", text)

        score, risk = calculate_privacy_score(emails, phones, passwords)

        self.email_label.setText(f"Emails: {len(emails)}")
        self.phone_label.setText(f"Phones: {len(phones)}")
        self.password_label.setText(f"Passwords: {len(passwords)}")

        self.score_label.setText(f"Score: {score}")
        self.risk_label.setText(f"Risk Level: {risk}")

    # BLUR
    def blur_image(self):
        if not self.current_file:
            self.output.append("\n⚠ Upload image first")
            return

        try:
            self.blurred_path = blur_sensitive_data(self.current_file)

            pixmap = QPixmap(self.blurred_path)
            self.image_preview.setPixmap(
                pixmap.scaled(500, 300, Qt.KeepAspectRatio)
            )

            self.output.append(f"\n🔥 Blur applied: {self.blurred_path}")

        except Exception as e:
            self.output.append(f"\n❌ Error: {str(e)}")

    # CLICK → ZOOM WINDOW
    def open_full_image(self, event):
        if self.blurred_path:
            viewer = ImageViewer(self.blurred_path)
            viewer.exec_()

    # REPORT
    def generate_report_ui(self):
        text = self.output.toPlainText()

        emails = re.findall(r"\S+@\S+", text)
        phones = re.findall(r"\b[6-9][0-9]{9}\b", text)
        passwords = re.findall(r"[a-zA-Z0-9@#]{6,}", text)

        score, risk = calculate_privacy_score(emails, phones, passwords)

        path = os.path.abspath("privacy_report.pdf")
        generate_report(path, text, score, risk)

        self.output.append(f"\n📄 Report saved: {path}")

    def dark_style(self):
        return """
        QWidget { background:#0d1117; color:white; }
        QPushButton { background:#238636; padding:10px; border-radius:8px; }
        QPushButton:hover { background:#2ea043; }
        QFrame { background:#161b22; border-radius:10px; padding:10px; }
        QTextEdit { background:#020617; border-radius:10px; padding:10px; }
        QLabel { font-size:14px; }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PrivacyExposureApp()
    window.show()
    sys.exit(app.exec_())