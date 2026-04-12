import sys
import os
import re
import pytesseract
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
from PyQt5.QtWidgets import QScrollArea

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QFileDialog, QVBoxLayout, QHBoxLayout, QFrame
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from privacy_score import calculate_privacy_score

# ---------- TESSERACT PATH ----------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------- POPPLER PATH ----------

POPPLER_PATH = r"C:\poppler\poppler-25.12.0\Library\bin"
# Example alternative:
# POPPLER_PATH = r"C:\poppler\Release-25.12.0-0\Library\bin"


# ---------- TEXT EXTRACTION (IMAGE + PDF) ----------
def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    # IMAGE FILES
    if ext in [".png", ".jpg", ".jpeg"]:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)

    # PDF FILES
    elif ext == ".pdf":
        # Try text-based PDF
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        # If empty → scanned PDF → OCR
        if text.strip() == "":
            images = convert_from_path(
                file_path,
                poppler_path=POPPLER_PATH
            )
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

        # 🔷 CONTENT AREA
        content = QFrame()
        content_layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        # TITLE
        title = QLabel("Privacy Exposure Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("title")

        # BUTTON
        self.upload_btn = QPushButton("Upload File (Image / PDF)")
        self.upload_btn.clicked.connect(self.load_file)

        # RESULT CARD
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

        # 🔷 TEXT OUTPUT (NEW 🔥)
        self.text_output = QLabel("Extracted Text will appear here...")
        self.text_output.setProperty("text_output", True)
        self.text_output.setWordWrap(True)
        self.text_output.setWordWrap(True)
        self.text_output.setStyleSheet("background:#0d1117; padding:10px; border-radius:8px;")

        # SCORE
        self.score_label = QLabel("Score: -")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setObjectName("score")

        # RISK
        self.risk_label = QLabel("Risk Level: -")
        self.risk_label.setAlignment(Qt.AlignCenter)
        self.risk_label.setObjectName("risk")

        # ADD CONTENT
        content_layout.addWidget(title)
        content_layout.addWidget(self.upload_btn)
        content_layout.addWidget(card)
        content_layout.addWidget(self.text_output)
        content_layout.addWidget(self.score_label)
        content_layout.addWidget(self.risk_label)

        content.setLayout(content_layout)
        scroll.setWidget(content)

        # ADD BOTH
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
        color: #f8fafc;
    }

    QPushButton {
        background-color: #22c55e;
        color: white;
        padding: 12px;
        border-radius: 12px;
        font-size: 14px;
        font-weight: bold;
    }

    QPushButton:hover {
        background-color: #16a34a;
    }

    /* SIDEBAR BUTTON STYLE */
    QPushButton {
        text-align: left;
        padding-left: 15px;
    }

    /* CARD STYLE */
    QFrame {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #111827,
            stop:1 #1f2937
        );
        border-radius: 15px;
        padding: 15px;
    }

    QLabel {
        font-size: 14px;
        margin: 6px;
    }

    /* TEXT OUTPUT BOX */
    QLabel[text_output="true"] {
        background-color: #020617;
        border-radius: 10px;
        padding: 12px;
    }

    #score {
        font-size: 26px;
        font-weight: bold;
        color: #22c55e;
    }

    #risk {
        font-size: 20px;
        font-weight: bold;
        color: #facc15;
    }
    """

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Supported Files (*.png *.jpg *.jpeg *.pdf)"
        )

        if not file_path:
            return

        # 🔷 SHOW LOADING
        self.text_output.setText("⏳ Processing file...")
        QApplication.processEvents()

        # EXTRACT TEXT
        text = extract_text_from_file(file_path)

        # SHOW TEXT (first 500 chars)
        self.text_output.setText(text[:500])

        # DETECTION
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        phones = re.findall(r"\b[6-9][0-9]{9}\b", text)

        raw_passwords = re.findall(r"[a-zA-Z0-9@#]{6,}", text)

        ignore_words = [
            "password", "account", "security", "change",
            "facebook", "instagram", "whatsapp",
            "telegram", "twitter", "gmail",
            "english", "create", "strong"
        ]

        passwords = []
        for pwd in raw_passwords:
            if pwd.lower() in ignore_words:
                continue
            if re.search(r"[0-9@#]", pwd):
                passwords.append(pwd)

        passwords = list(set(passwords))

        # SCORE
        score, risk, _ = calculate_privacy_score(
            emails, phones, passwords, unsafe_image=False
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
