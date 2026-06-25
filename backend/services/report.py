"""
Report Service — 6 Report Types
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

# ── Palette ──────────────────────────────────────────────────────────────────
DARK   = colors.HexColor("#0d1117")
ACCENT = colors.HexColor("#58a6ff")
DANGER = colors.HexColor("#f85149")
WARN   = colors.HexColor("#d29922")
OK     = colors.HexColor("#238636")
PANEL  = colors.HexColor("#161b22")
GRAY   = colors.HexColor("#8b949e")
RED2   = colors.HexColor("#dc2626")

def _risk_color(r):
    return RED2 if r=="CRITICAL" else DANGER if r=="HIGH" else WARN if r=="MEDIUM" else OK

def _styles():
    s = getSampleStyleSheet()
    T = ParagraphStyle("T", parent=s["Heading1"], fontSize=22, textColor=ACCENT, spaceAfter=4)
    S = ParagraphStyle("S", parent=s["Normal"],   fontSize=10, textColor=GRAY, spaceAfter=16)
    H = ParagraphStyle("H", parent=s["Heading2"], fontSize=13, textColor=ACCENT, spaceBefore=16, spaceAfter=6)
    B = ParagraphStyle("B", parent=s["Normal"],   fontSize=9,  textColor=colors.black, spaceAfter=3)
    I = ParagraphStyle("I", parent=s["Normal"],   fontSize=9,  textColor=colors.black, leftIndent=10, spaceAfter=2)
    return T, S, H, B, I

def _doc(path):
    return SimpleDocTemplate(path, pagesize=letter,
        leftMargin=0.7*inch, rightMargin=0.7*inch,
        topMargin=0.7*inch, bottomMargin=0.7*inch)

def _count(findings, ftype):
    return sum(1 for f in findings if f.get("type")==ftype)

def _header(story, title, subtitle, T, S):
    story.append(Paragraph(title, T))
    story.append(Paragraph(subtitle, S))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(Spacer(1, 10))

def _summary_table(story, score, risk, findings, H):
    story.append(Paragraph("Exposure Summary", H))
    rc = _risk_color(risk)
    data = [
        ["Score","Risk","Password","Aadhaar","PAN","CC/CVV","OTP","DOB","Email","Phone","Faces","ID Doc"],
        [
            str(int(score)), risk,
            str(_count(findings,"password")), str(_count(findings,"aadhaar")),
            str(_count(findings,"pan_card")),
            str(_count(findings,"credit_card")+_count(findings,"cvv")),
            str(_count(findings,"otp")), str(_count(findings,"dob")),
            str(_count(findings,"email")), str(_count(findings,"phone")),
            str(_count(findings,"face_detected")), str(_count(findings,"id_card_visible")),
        ]
    ]
    cw = 0.6*inch
    t = Table(data, colWidths=[cw]*12)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),PANEL), ("TEXTCOLOR",(0,0),(-1,0),ACCENT),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,0),7),
        ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#f0f6fc")),
        ("TEXTCOLOR",(0,1),(0,1),rc), ("TEXTCOLOR",(1,1),(1,1),rc),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"), ("FONTSIZE",(0,1),(-1,1),10),
        ("ALIGN",(0,0),(-1,-1),"CENTER"), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d0d7de")),
        ("BOX",(0,0),(-1,-1),1,ACCENT),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(t)
    story.append(Spacer(1,10))

def _findings_table(story, findings, H, B):
    if not findings: return
    story.append(Paragraph("Detected Sensitive Data", H))
    rows = [["#","Type","Method","Value"]]
    for i,f in enumerate(findings,1):
        rows.append([str(i), f.get("type","").upper(), f.get("method","regex"), str(f.get("value",""))[:80]])
    t = Table(rows, colWidths=[0.35*inch,1.1*inch,0.6*inch,5.0*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),PANEL), ("TEXTCOLOR",(0,0),(-1,0),ACCENT),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f6f8fa")]),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d0d7de")),
        ("ALIGN",(0,0),(2,-1),"CENTER"),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(t)
    story.append(Spacer(1,10))

def _recommendations_section(story, recs, H, B, I):
    if not recs: return
    story.append(Paragraph("Security Recommendations", H))
    for rec in recs:
        sev = rec.get("severity","LOW")
        hex_ = "#f85149" if sev=="HIGH" else "#d29922" if sev=="MEDIUM" else "#238636"
        story.append(Paragraph(f'<font color="{hex_}"><b>[{sev}]</b></font> {rec.get("title","")}', B))
        for a in rec.get("advice",[]):
            story.append(Paragraph(f"• {a}", I))
        story.append(Spacer(1,4))

# ════════════════════════════════════════════════════════════════════════════
# Phase 17 — Cover Page Helper
# ════════════════════════════════════════════════════════════════════════════
def _cover_page(story, title, subtitle, scan_file, score, risk_level, T, S):
    """Branded cover page with risk gauge and executive summary."""
    rc = _risk_color(risk_level)
    story.append(Spacer(1, 0.4 * inch))
    brand = ParagraphStyle("Brand", fontSize=28, textColor=ACCENT,
                           fontName="Helvetica-Bold", alignment=1,
                           leading=34, spaceAfter=10)
    tag   = ParagraphStyle("Tag",   fontSize=12, textColor=GRAY,
                           fontName="Helvetica",       alignment=1,
                           leading=16, spaceAfter=16)
    story.append(Paragraph("PrivacyShield", brand))
    story.append(Paragraph("Privacy Exposure Score Tool", tag))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 0.25 * inch))

    # title_style: dark readable color (NOT near-white — PDF background is white)
    title_style = ParagraphStyle("CTitle", fontSize=20,
                                  textColor=colors.HexColor("#24292f"),
                                  fontName="Helvetica-Bold", alignment=1,
                                  leading=26, spaceAfter=12)
    sub_style   = ParagraphStyle("CSub",   fontSize=11, textColor=GRAY,
                                  fontName="Helvetica", alignment=1,
                                  leading=15, spaceAfter=20)
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(subtitle, sub_style))

    # Score gauge table
    gauge_data = [["Privacy Score", "Risk Level", "Generated", "File"]]
    gauge_data.append([
        f"{int(score)} / 100",
        risk_level,
        datetime.now().strftime("%Y-%m-%d  %H:%M"),
        (scan_file[:38] + "...") if scan_file and len(scan_file) > 38 else (scan_file or "--"),
    ])
    gt = Table(gauge_data, colWidths=[1.5*inch, 1.5*inch, 2.0*inch, 2.1*inch])
    gt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PANEL),
        ("TEXTCOLOR",  (0,0), (-1,0), ACCENT),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 9),
        ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#f0f6fc")),
        ("TEXTCOLOR",  (0,1), (0,1),  rc),
        ("TEXTCOLOR",  (1,1), (1,1),  rc),
        ("FONTNAME",   (0,1), (1,1),  "Helvetica-Bold"),
        ("FONTSIZE",   (0,1), (0,1),  18),
        ("FONTSIZE",   (1,1), (1,1),  14),
        ("FONTSIZE",   (2,1), (-1,1), 10),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("GRID",       (0,0), (-1,-1), 0.5, ACCENT),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(gt)
    story.append(Spacer(1, 0.18 * inch))

    # Executive summary box
    risk_desc = {
        "CRITICAL": "CRITICAL RISK — This document contains extremely sensitive data (Aadhaar/PAN/card/password). Immediate action required to prevent identity theft or financial fraud.",
        "HIGH":     "HIGH RISK — Multiple sensitive data points detected. Prompt remediation strongly recommended.",
        "MEDIUM":   "MEDIUM RISK — Some sensitive information detected. Review and redact before sharing.",
        "LOW":      "LOW RISK — Minor data exposure detected. Consider redacting for added protection.",
        "SAFE":     "SAFE — No significant privacy risks detected in this document.",
    }
    exec_text = risk_desc.get(risk_level, "Privacy analysis complete.")
    exec_style = ParagraphStyle("Exec", fontSize=10, textColor=colors.HexColor("#24292f"),
                                 fontName="Helvetica", leading=16)
    exec_box = Table(
        [[Paragraph(f"<b>Executive Summary</b><br/>{exec_text}", exec_style)]],
        colWidths=[7.1 * inch]
    )
    exec_box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#f6f8fa")),
        ("BOX",           (0,0), (-1,-1), 2, rc),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("RIGHTPADDING",  (0,0), (-1,-1), 14),
    ]))
    story.append(exec_box)
    story.append(Spacer(1, 0.15 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(Spacer(1, 10))


# ════════════════════════════════════════════════════════════════════════════
# 1. Privacy Exposure Report  (Phase 17 — with Cover Page)
# ════════════════════════════════════════════════════════════════════════════
def generate_full_report(output_path, filename, text, score, risk_level, findings, recommendations):
    T, S, H, B, I = _styles()
    doc = _doc(output_path)
    story = []
    _cover_page(story, "Privacy Exposure Report",
                "Full PII Analysis · Findings · Security Recommendations",
                filename, score, risk_level, T, S)
    _summary_table(story, score, risk_level, findings, H)
    _findings_table(story, findings, H, B)
    _recommendations_section(story, recommendations, H, B, I)
    if text:
        story.append(Paragraph("Extracted Text (OCR)", H))
        for line in text.split("\n")[:40]:
            if line.strip():
                story.append(Paragraph(line[:120].replace("<", "&lt;").replace(">", "&gt;"), B))
    doc.build(story)
    return output_path


# ════════════════════════════════════════════════════════════════════════════
# 2. Sensitive Data Summary Report
# ════════════════════════════════════════════════════════════════════════════
def generate_sensitive_summary(output_path, filename, score, risk_level, findings):
    T,S,H,B,I = _styles()
    doc = _doc(output_path)
    story = []
    _header(story, "Sensitive Data Summary",
            f"File: <b>{filename}</b> &nbsp;|&nbsp; Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", T, S)
    _summary_table(story, score, risk_level, findings, H)

    # Group by type
    by_type = {}
    for f in findings:
        by_type.setdefault(f.get("type","unknown"), []).append(f.get("value",""))

    story.append(Paragraph("Findings by Category", H))
    for ftype, vals in sorted(by_type.items()):
        story.append(Paragraph(f"<b>{ftype.upper().replace('_',' ')}</b> — {len(vals)} item(s)", B))
        for v in vals[:10]:
            story.append(Paragraph(f"&nbsp;&nbsp;• {str(v)[:100]}", I))
        if len(vals) > 10:
            story.append(Paragraph(f"&nbsp;&nbsp;... and {len(vals)-10} more", I))
        story.append(Spacer(1,4))

    doc.build(story)
    return output_path


# ════════════════════════════════════════════════════════════════════════════
# 3. Metadata Report
# ════════════════════════════════════════════════════════════════════════════
def generate_metadata_report(output_path, filename, score, risk_level, findings,
                              upload_date, source, informational=None, recommendations=None):
    """Professionalized metadata report with categorization and recommendations."""
    T,S,H,B,I = _styles()
    doc = _doc(output_path)
    story = []
    
    _header(story, "Privacy Metadata Analysis",
            f"Document Privacy Audit: <b>{filename}</b>", T, S)

    # 1. Summary Score Card
    story.append(Paragraph("Privacy Exposure Summary", H))
    risk_color = "#dc2626" if risk_level == "CRITICAL" else "#ef4444" if risk_level == "HIGH" else "#f59e0b" if risk_level == "MEDIUM" else "#22c55e"
    
    summary_data = [
        ["Overall Privacy Score", f"{int(score)} / 100"],
        ["Risk Assessment", risk_level],
        ["Sensitive Findings", str(len(findings))],
        ["Document Type", str(source or "File").replace("metadata_", "").upper()]
    ]
    t_summary = Table(summary_data, colWidths=[2.5*inch, 4.6*inch])
    t_summary.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#f8fafc")),
        ("TEXTCOLOR",(1,1),(1,1),colors.HexColor(risk_color)),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#e2e8f0")),
        ("TOPPADDING",(0,0),(-1,-1),8), ("BOTTOMPADDING",(0,0),(-1,-1),8),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 20))

    # 2. Sensitive Privacy Findings
    if findings:
        story.append(Paragraph("Sensitive Metadata Findings", H))
        story.append(Paragraph("These fields directly leak personal or device identity information.", S))
        
        rows = [["Risk Level", "Metadata Field", "Detected Value"]]
        for f in findings:
            rows.append([
                f.get("risk", "MEDIUM"),
                f.get("label", f.get("field", "Unknown")),
                str(f.get("value", ""))[:60]
            ])
            
        t_sensitive = Table(rows, colWidths=[1.2*inch, 2.0*inch, 3.9*inch])
        t_sensitive.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1e293b")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f1f5f9")]),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ]))
        story.append(t_sensitive)
        
        # Risk Explanations
        story.append(Spacer(1, 10))
        story.append(Paragraph("Risk Explanations:", B))
        for f in findings:
            if f.get("reason"):
                story.append(Paragraph(f"• <b>{f.get('label')}:</b> {f.get('reason')}", I))
        
        story.append(Spacer(1, 20))

    # 3. Informational Metadata
    if informational:
        story.append(Paragraph("General Document Information", H))
        story.append(Paragraph("These fields are technical and do not significantly impact privacy risk.", S))
        
        info_rows = []
        # Chunk into pairs for compact layout
        for i in range(0, len(informational), 2):
            row = []
            f1 = informational[i]
            row.extend([f1.get("label", ""), str(f1.get("value", ""))[:30]])
            if i+1 < len(informational):
                f2 = informational[i+1]
                row.extend([f2.get("label", ""), str(f2.get("value", ""))[:30]])
            else:
                row.extend(["", ""])
            info_rows.append(row)
            
        t_info = Table(info_rows, colWidths=[1.5*inch, 2.0*inch, 1.5*inch, 2.1*inch])
        t_info.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e2e8f0")),
            ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
            ("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#f8fafc")),
            ("BACKGROUND",(2,0),(2,-1),colors.HexColor("#f8fafc")),
            ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ]))
        story.append(t_info)
        story.append(Spacer(1, 20))

    # 4. Recommendations
    if recommendations:
        story.append(Paragraph("Security Recommendations", H))
        for rec in recommendations:
            story.append(Paragraph(f"<b>{rec.get('title')}</b>", B))
            for advice in rec.get("advice", []):
                story.append(Paragraph(f"→ {advice}", I))
            story.append(Spacer(1, 8))

    doc.build(story)
    return output_path



# ════════════════════════════════════════════════════════════════════════════
# 4. Attack Simulation Report
# ════════════════════════════════════════════════════════════════════════════
_ATTACK_MAP = {
    "email":          ("Phishing / Credential Stuffing", "HIGH",
                       ["Attacker sends targeted phishing emails using your address.",
                        "Email used for credential stuffing across 1000s of sites.",
                        "Account takeover if password reuse is detected."]),
    "phone":          ("SIM Swap / Vishing", "HIGH",
                       ["SIM swap attack to intercept OTPs and 2FA codes.",
                        "Vishing (voice phishing) calls impersonating your bank.",
                        "WhatsApp / Telegram account takeover via OTP interception."]),
    "password":       ("Direct Account Takeover", "CRITICAL",
                       ["Immediate login to any account using the exposed password.",
                        "Password spraying across banking, email, social media.",
                        "Lateral movement if password is reused across services."]),
    "aadhaar":        ("Identity Fraud / KYC Bypass", "CRITICAL",
                       ["Full identity cloning using Aadhaar number.",
                        "KYC bypass for financial products (loans, credit cards).",
                        "Fraudulent SIM registration in your name."]),
    "pan_card":       ("Tax / Financial Fraud", "CRITICAL",
                       ["Filing fraudulent income tax returns in your name.",
                        "Applying for loans using your PAN as identity proof.",
                        "Opening fake financial accounts."]),
    "credit_card":    ("Financial Theft", "CRITICAL",
                       ["Unauthorized online purchases using card number.",
                        "Card-not-present (CNP) fraud on e-commerce sites.",
                        "Dark web sale of card data."]),
    "cvv":            ("Immediate Card Fraud", "CRITICAL",
                       ["Complete card fraud capability with number + CVV.",
                        "Bypass card verification on international transactions.",
                        "Instant purchases on sites that don't require 3D Secure."]),
    "otp":            ("2FA Bypass", "HIGH",
                       ["One-time bypass of 2-factor authentication.",
                        "Authorization of pending transactions.",
                        "Account recovery using intercepted OTP."]),
    "dob":            ("Identity Correlation", "MEDIUM",
                       ["Combined with name/address for full identity profiling.",
                        "Security question bypass on banking portals.",
                        "Used to verify identity in social engineering calls."]),
    "face_detected":  ("Biometric Spoofing", "HIGH",
                       ["Deepfake generation from face data for video KYC bypass.",
                        "Face recognition database correlation.",
                        "Social media profile linking and stalking."]),
    "id_card_visible":("Document Forgery", "CRITICAL",
                       ["High-quality scan enables document cloning.",
                        "Forged ID card creation for in-person fraud.",
                        "Used in conjunction with other data for full identity fraud."]),
    "person_name":    ("Social Engineering", "MEDIUM",
                       ["Targeted spear-phishing using your real name.",
                        "Impersonation of you in communications to employers or family.",
                        "Profile building for targeted scams."]),
    "location":       ("Physical Threat", "MEDIUM",
                       ["Home address enables physical stalking.",
                        "Targeted burglary during known travel periods.",
                        "Doxxing (public exposure of personal address)."]),
}

def generate_attack_simulation(output_path, filename, score, risk_level, findings):
    T,S,H,B,I = _styles()
    doc = _doc(output_path)
    story = []
    _header(story, "Attack Simulation Report",
            f"Simulated attack vectors for exposed data in: <b>{filename}</b>", T, S)

    story.append(Paragraph(
        '<font color="#f85149"><b>⚠ This report simulates how an attacker could exploit the detected data. '
        'It is generated for defensive awareness only.</b></font>', B))
    story.append(Spacer(1,8))
    _summary_table(story, score, risk_level, findings, H)

    seen_types = set()
    attacks = []
    for f in findings:
        ft = f.get("type","")
        if ft in _ATTACK_MAP and ft not in seen_types:
            seen_types.add(ft)
            attacks.append((ft, _ATTACK_MAP[ft]))

    if attacks:
        story.append(Paragraph("Simulated Attack Vectors", H))
        for ft,(attack_name,sev,steps) in attacks:
            hex_ = "#dc2626" if sev=="CRITICAL" else "#f85149" if sev=="HIGH" else "#d29922" if sev=="MEDIUM" else "#238636"
            story.append(Paragraph(
                f'<font color="{hex_}"><b>[{sev}]</b></font> <b>{attack_name}</b>'
                f' <font color="#8b949e">← via {ft.replace("_"," ").upper()}</font>', B))
            for step in steps:
                story.append(Paragraph(f"&nbsp;&nbsp;→ {step}", I))
            story.append(Spacer(1,6))

    story.append(Spacer(1,10))
    story.append(Paragraph("Defensive Actions", H))
    story.append(Paragraph("• Immediately redact this document using the Blur Engine.", B))
    story.append(Paragraph("• Change all exposed passwords and enable 2FA on all accounts.", B))
    story.append(Paragraph("• Contact your bank if financial data (card/CVV/OTP) was found.", B))
    story.append(Paragraph("• Report identity fraud to UIDAI, NPCI, or local cybercrime cell.", B))
    story.append(Paragraph("• Run a breach check at haveibeenpwned.com for your email.", B))

    doc.build(story)
    return output_path


# ════════════════════════════════════════════════════════════════════════════
# 5. Score History Report
# ════════════════════════════════════════════════════════════════════════════
def generate_score_history(output_path, scans):
    """scans: list of ScanRecord dicts with id, filename, score, risk_level, upload_date, findings count"""
    T,S,H,B,I = _styles()
    doc = _doc(output_path)
    story = []
    _header(story, "Score History Report",
            f"File upload scan history — Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", T, S)

    if not scans:
        story.append(Paragraph("No scan history available.", B))
        doc.build(story); return output_path

    # Stats
    scores = [s.get("score",0) for s in scans]
    avg = sum(scores)/len(scores)
    critical = sum(1 for s in scans if s.get("risk_level")=="CRITICAL")
    high     = sum(1 for s in scans if s.get("risk_level")=="HIGH")

    story.append(Paragraph("Summary Statistics", H))
    stats_rows = [
        ["Total Scans","Average Score","Highest Score","Lowest Score","Critical","High Risk"],
        [str(len(scans)), f"{avg:.1f}", f"{max(scores):.0f}",
         f"{min(scores):.0f}", str(critical), str(high)]
    ]
    t = Table(stats_rows, colWidths=[1.2*inch]*6)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),PANEL), ("TEXTCOLOR",(0,0),(-1,0),ACCENT),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
        ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#f0f6fc")),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"), ("FONTSIZE",(0,1),(-1,1),13),
        ("ALIGN",(0,0),(-1,-1),"CENTER"), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d0d7de")),
        ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    story.append(t)
    story.append(Spacer(1,12))

    story.append(Paragraph("All Scans", H))
    rows = [["#","Filename","Date","Score","Risk","Findings"]]
    # Use sequential row numbers (1,2,3...) — NOT database IDs
    for i, s in enumerate(scans, 1):
        rows.append([
            str(i),
            str(s.get("filename",""))[:35],
            str(s.get("upload_date",""))[:16],
            str(int(s.get("score",0))),
            s.get("risk_level","LOW"),
            str(s.get("finding_count", len(s.get("findings",[]))))
        ])
    t2 = Table(rows, colWidths=[0.4*inch,2.2*inch,1.5*inch,0.6*inch,0.8*inch,0.7*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),PANEL), ("TEXTCOLOR",(0,0),(-1,0),ACCENT),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f6f8fa")]),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d0d7de")),
        ("ALIGN",(0,0),(0,-1),"CENTER"), ("ALIGN",(3,0),(5,-1),"CENTER"),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(t2)
    doc.build(story)
    return output_path


# ════════════════════════════════════════════════════════════════════════════
# 6. Batch Scan Report
# ════════════════════════════════════════════════════════════════════════════
def generate_batch_report(output_path, scans_data):
    """scans_data: list of dicts {scan, findings, recommendations}"""
    T,S,H,B,I = _styles()
    doc = _doc(output_path)
    story = []
    _header(story, "Batch Scan Report",
            f"Combined analysis of {len(scans_data)} scan(s) — Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", T, S)

    all_findings = [f for sd in scans_data for f in sd.get("findings",[])]
    scores = [sd["scan"].get("score",0) for sd in scans_data if "scan" in sd]
    risks  = [sd["scan"].get("risk_level","LOW") for sd in scans_data if "scan" in sd]

    # Aggregate summary
    story.append(Paragraph("Aggregate Summary", H))
    agg_rows = [
        ["Files","Total Findings","Avg Score","Critical","High","Medium","Low"],
        [
            str(len(scans_data)), str(len(all_findings)),
            f"{(sum(scores)/len(scores) if scores else 0):.1f}",
            str(risks.count("CRITICAL")), str(risks.count("HIGH")),
            str(risks.count("MEDIUM")), str(risks.count("LOW")),
        ]
    ]
    t = Table(agg_rows, colWidths=[0.85*inch]*7)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),PANEL), ("TEXTCOLOR",(0,0),(-1,0),ACCENT),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
        ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#f0f6fc")),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"), ("FONTSIZE",(0,1),(-1,1),12),
        ("ALIGN",(0,0),(-1,-1),"CENTER"), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d0d7de")),
        ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    story.append(t)
    story.append(Spacer(1,12))

    # Per-file section
    for sd in scans_data:
        sc = sd.get("scan",{})
        fds = sd.get("findings",[])
        risk = sc.get("risk_level","LOW")
        risk_hex = {"CRITICAL":"dc2626","HIGH":"f85149","MEDIUM":"d29922","LOW":"238636"}.get(risk,"238636")
        story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
        story.append(Spacer(1,6))
        story.append(Paragraph(
            f'<b>{sc.get("filename","")}</b> &nbsp;'
            f'Score: <font color="#{risk_hex}">{int(sc.get("score",0))}</font> &nbsp;'
            f'Risk: <font color="#{risk_hex}">{risk}</font> &nbsp;'
            f'Findings: {len(fds)}', B))

        if fds:
            rows = [["Type","Value"]]
            for f in fds[:15]:
                rows.append([f.get("type","").upper(), str(f.get("value",""))[:80]])
            if len(fds) > 15:
                rows.append(["...","and more"])
            t2 = Table(rows, colWidths=[1.3*inch,5.8*inch])
            t2.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),PANEL), ("TEXTCOLOR",(0,0),(-1,0),ACCENT),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f6f8fa")]),
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#d0d7de")),
                ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ]))
            story.append(t2)
        story.append(Spacer(1,8))

    doc.build(story)
    return output_path


# ════════════════════════════════════════════════════════════════════════════
# 7. Remediation Action Plan Report  (Phase 17)
# ════════════════════════════════════════════════════════════════════════════
_URGENCY_COLOR = {
    "IMMEDIATE":   colors.HexColor("#dc2626"),
    "WITHIN_24H":  colors.HexColor("#ea580c"),
    "WITHIN_WEEK": colors.HexColor("#ca8a04"),
}
_FINDING_LABEL = {
    "aadhaar": "Aadhaar Number", "pan_card": "PAN Card", "credit_card": "Credit Card",
    "cvv": "CVV Code", "password": "Password", "email": "Email Address",
    "phone": "Phone Number", "otp": "OTP / 2FA Code", "dob": "Date of Birth",
    "face_detected": "Face / Biometric", "id_card_visible": "Government ID Card",
}

def generate_remediation_pdf(output_path, filename, score, risk_level, remediation_plan):
    """
    Generates a printable PDF of the full remediation action plan.
    remediation_plan: dict returned by services.remediation.generate_remediation_plan()
    """
    T, S, H, B, I = _styles()
    doc = _doc(output_path)
    story = []

    _cover_page(story, "Remediation Action Plan",
                "Step-by-step fix guide with legal references",
                filename, score, risk_level, T, S)

    plans = remediation_plan.get("plans", [])
    legal = remediation_plan.get("legal_summary", [])
    imm   = remediation_plan.get("immediate_actions", 0)

    # Summary stats
    story.append(Paragraph("Plan Summary", H))
    stat_rows = [
        ["Finding Types", "Immediate Actions", "Laws Referenced", "Risk Level"],
        [str(len(plans)), str(imm), str(len(legal)), risk_level],
    ]
    st = Table(stat_rows, colWidths=[1.8*inch, 1.8*inch, 1.8*inch, 1.8*inch])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PANEL), ("TEXTCOLOR", (0,0), (-1,0), ACCENT),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 10),
        ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#f0f6fc")),
        ("FONTNAME",   (0,1), (-1,1), "Helvetica-Bold"), ("FONTSIZE", (0,1), (-1,1), 14),
        ("TEXTCOLOR",  (3,1), (3,1),  _risk_color(risk_level)),
        ("ALIGN", (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.4, ACCENT),
        ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(st)
    story.append(Spacer(1, 14))

    # Per-finding sections
    step_style = ParagraphStyle("Step", fontSize=9, textColor=colors.black,
                                leftIndent=10, spaceAfter=3, leading=14)
    for plan in plans:
        ftype   = plan.get("finding_type", "")
        label   = _FINDING_LABEL.get(ftype, ftype.replace("_", " ").title())
        urg     = plan.get("urgency", "WITHIN_WEEK")
        uc      = _URGENCY_COLOR.get(urg, WARN)
        urg_lbl = plan.get("urgency_label", urg)
        count   = plan.get("count", 1)

        hdr_data = [[f"{label}  ({count} instance{'s' if count > 1 else ''} found)",
                     f"[{urg}]  {urg_lbl}"]]
        ht = Table(hdr_data, colWidths=[4.5*inch, 2.6*inch])
        ht.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), PANEL),
            ("TEXTCOLOR",     (0,0), (0,0),   ACCENT),
            ("FONTNAME",      (0,0), (0,0),   "Helvetica-Bold"), ("FONTSIZE", (0,0), (0,0), 11),
            ("TEXTCOLOR",     (1,0), (1,0),   uc),
            ("FONTNAME",      (1,0), (1,0),   "Helvetica-Bold"), ("FONTSIZE", (1,0), (1,0), 9),
            ("ALIGN",         (1,0), (1,0),   "RIGHT"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ]))
        story.append(ht)

        for j, step in enumerate(plan.get("steps", []), 1):
            story.append(Paragraph(
                f'<font color="#58a6ff"><b>Step {j}:</b></font> {step}', step_style
            ))

        refs = plan.get("legal_refs", [])
        if refs:
            ref_rows = [["Law", "Section", "Note"]]
            for r in refs:
                ref_rows.append([r.get("law", ""), r.get("section", ""), r.get("note", "")])
            rt = Table(ref_rows, colWidths=[1.8*inch, 1.0*inch, 4.3*inch])
            rt.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#fff8e1")),
                ("TEXTCOLOR",  (0,0), (-1,0), colors.HexColor("#b45309")),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 8),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#fffbeb")]),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d7de")),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(rt)

        story.append(Spacer(1, 10))

    # Legal summary footer
    if legal:
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
        story.append(Paragraph("Applicable Privacy Laws", H))
        law_rows = [["Law", "Section"]]
        for l in legal:
            law_rows.append([l.get("law", ""), l.get("section", "")])
        lt = Table(law_rows, colWidths=[3.5*inch, 3.6*inch])
        lt.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#fff8e1")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.HexColor("#b45309")),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#fffbeb")]),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d7de")),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(lt)

    doc.build(story)
    return output_path
