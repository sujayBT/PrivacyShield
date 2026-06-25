from reportlab.lib.pagesizes import letter # type: ignore
from reportlab.pdfgen import canvas


def generate_report(output_path, text, score, risk):
    c = canvas.Canvas(output_path, pagesize=letter)

    c.setFont("Helvetica", 12)

    # Title
    c.drawString(200, 750, "Privacy Exposure Report")

    # Score
    c.drawString(50, 700, f"Score: {score}")
    c.drawString(50, 680, f"Risk Level: {risk}")

    # Text content
    y = 650
    lines = text.split("\n")

    for line in lines[:30]:
        c.drawString(50, y, line[:90])
        y -= 15

    c.save()

    return output_path