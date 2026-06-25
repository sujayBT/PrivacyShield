"""
Recommendations Service — Phase 3 Update
==========================================
Now handles all 16 finding types:
  Regex (9): email, phone, password, aadhaar, pan_card, credit_card, cvv, dob, otp
  AI/NER (7): person_name, location, organization, id_number, date, financial, demographic
"""

from typing import List


# ─── Per-Type Advice Templates ───────────────────────────────────────────────

_TYPE_ADVICE = {
    "email": {
        "category": "Email Address Exposure",
        "icon": "mail",
        "severity_fn": lambda count: "HIGH" if count > 2 else "MEDIUM",
        "title_fn": lambda count: f"{count} email address(es) detected",
        "advice": [
            "Never include your email in publicly shared documents or screenshots.",
            "Use masked email services (Apple Hide My Email, SimpleLogin) for registrations.",
            "Redact email addresses using the Blur Engine before sharing files.",
            "Enable two-factor authentication on all exposed email accounts immediately.",
            "Check haveibeenpwned.com to see if your email has been in a data breach.",
        ],
    },
    "phone": {
        "category": "Phone Number Exposure",
        "icon": "phone",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"{count} phone number(s) detected",
        "advice": [
            "Never share your phone number in documents that may be publicly accessible.",
            "Use a secondary/virtual number for online registrations (e.g., Google Voice).",
            "Request data brokers remove your phone number from their databases.",
            "Contact your carrier to set up a PIN to prevent SIM-swapping attacks.",
        ],
    },
    "password": {
        "category": "Password / Credential Exposure",
        "icon": "key",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"{count} potential password(s) detected — change them immediately",
        "advice": [
            "Change all exposed passwords IMMEDIATELY across every account that uses them.",
            "Use a reputable password manager (Bitwarden, 1Password) to generate strong passwords.",
            "Never write down or screenshot passwords.",
            "Enable two-factor authentication wherever possible.",
            "Ensure each account uses a unique password.",
            "Run a breach check at haveibeenpwned.com for your accounts.",
        ],
    },
    "aadhaar": {
        "category": "Aadhaar Number Exposure",
        "icon": "shield",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"{count} Aadhaar number(s) detected — critical national ID",
        "advice": [
            "Aadhaar is your unique national identity — treat it like a government secret.",
            "Use the masked Aadhaar option (shows only last 4 digits) for non-essential verifications.",
            "File a complaint at UIDAI (uidai.gov.in) if you believe your Aadhaar was misused.",
            "Redact your Aadhaar number immediately from any shared documents using the Blur Engine.",
            "Never share full Aadhaar numbers over email, chat, or unencrypted documents.",
        ],
    },
    "pan_card": {
        "category": "PAN Card Number Exposure",
        "icon": "shield",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"{count} PAN card number(s) detected",
        "advice": [
            "PAN card numbers can be misused for identity fraud and financial crimes.",
            "Immediately redact PAN numbers from any documents before sharing.",
            "If exposed publicly, report it to the Income Tax Department (incometax.gov.in).",
            "Monitor your CIBIL/credit score for unusual activity.",
            "Never share PAN details over WhatsApp, email, or unencrypted storage.",
        ],
    },
    "credit_card": {
        "category": "Credit/Debit Card Number Exposure",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"{count} credit/debit card number(s) detected",
        "advice": [
            "Contact your bank IMMEDIATELY to block and reissue any exposed card.",
            "Monitor your bank statements for unauthorized transactions.",
            "Never photograph or screenshot your physical card.",
            "Use virtual cards for online transactions (most banks offer this).",
            "File a fraud report with your bank if you suspect misuse.",
        ],
    },
    "cvv": {
        "category": "CVV Code Exposure",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"{count} CVV code(s) detected — replace your card now",
        "advice": [
            "Call your bank now to request a card replacement — CVV exposure means your card is compromised.",
            "CVV codes should NEVER appear in any document, screenshot, or message.",
            "Enable transaction notifications on your card to catch unauthorized use.",
            "Use virtual card numbers (offered by many banks) for online payments.",
        ],
    },
    "dob": {
        "category": "Date of Birth Exposure",
        "icon": "shield",
        "severity_fn": lambda count: "MEDIUM",
        "title_fn": lambda count: f"{count} date(s) of birth detected",
        "advice": [
            "Date of birth combined with other data enables identity theft.",
            "Remove date of birth from public profiles and documents where not required.",
            "Be cautious about sharing DOB with websites — check their privacy policy.",
            "Avoid storing DOB in unencrypted documents.",
        ],
    },
    "otp": {
        "category": "OTP / Passcode Exposure",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"{count} OTP/passcode(s) detected",
        "advice": [
            "OTPs are single-use authentication codes — never screenshot or forward them.",
            "If an OTP was captured in a document, that session may have been compromised.",
            "Always use OTPs only in the app/website that requested them.",
            "Enable OTP expiry alerts from your bank or service provider.",
        ],
    },
    # ── AI NER Types ─────────────────────────────────────────────────────────
    "person_name": {
        "category": "Personal Name Exposure (AI Detected)",
        "icon": "shield",
        "severity_fn": lambda count: "MEDIUM",
        "title_fn": lambda count: f"{count} personal name(s) identified by AI",
        "advice": [
            "Full names in documents enable social engineering and identity correlation.",
            "Redact full names from files before sharing publicly using the Blur Engine.",
            "Audit who has access to documents containing personal names.",
            "Consider using initials or aliases in non-formal communications.",
            "Review privacy settings on platforms where this document may be shared.",
        ],
    },
    "location": {
        "category": "Location / Address Exposure (AI Detected)",
        "icon": "shield",
        "severity_fn": lambda count: "MEDIUM",
        "title_fn": lambda count: f"{count} location(s) identified by AI",
        "advice": [
            "Home addresses and city-level data enable physical stalking and targeted fraud.",
            "Remove precise addresses from publicly accessible documents.",
            "Use only city/region in public profiles — avoid street-level detail.",
            "Review location permissions on apps that may share this data.",
            "Consider using a PO Box or virtual address for public correspondence.",
        ],
    },
    "organization": {
        "category": "Organization Name Exposure (AI Detected)",
        "icon": "shield",
        "severity_fn": lambda count: "LOW",
        "title_fn": lambda count: f"{count} organization name(s) identified by AI",
        "advice": [
            "Organization names in combination with other data can enable targeted phishing.",
            "Be aware that your workplace information can be exploited in spear-phishing attacks.",
            "Limit publicly visible employer information on social media profiles.",
            "Verify document recipients before sharing files containing company affiliations.",
        ],
    },
    "id_number": {
        "category": "Numeric ID / Reference Exposure (AI Detected)",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "MEDIUM",
        "title_fn": lambda count: f"{count} numeric identifier(s) identified by AI",
        "advice": [
            "Numeric IDs flagged by AI may be account numbers, policy IDs, or reference codes.",
            "Review each flagged number to confirm whether it's sensitive.",
            "Redact any confirmed ID numbers before sharing the document.",
            "Contact the issuing authority if a government ID number was exposed.",
        ],
    },
    "date": {
        "category": "Date Information Exposure (AI Detected)",
        "icon": "shield",
        "severity_fn": lambda count: "LOW",
        "title_fn": lambda count: f"{count} date(s) identified by AI",
        "advice": [
            "Dates in combination with names and IDs can enable identity verification bypass.",
            "Confirm whether any flagged dates are dates of birth or sensitive milestones.",
            "Redact sensitive dates from documents shared publicly.",
        ],
    },
    "financial": {
        "category": "Financial Information Exposure (AI Detected)",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "HIGH" if count > 1 else "MEDIUM",
        "title_fn": lambda count: f"{count} financial data point(s) identified by AI",
        "advice": [
            "Financial figures (salaries, amounts, transactions) can enable fraud and extortion.",
            "Never share financial documents without redacting specific amounts.",
            "Monitor your bank accounts for unusual activity if financial data was exposed.",
            "Report suspected financial fraud to your bank and local cybercrime cell.",
        ],
    },
    "demographic": {
        "category": "Demographic Information Exposure (AI Detected)",
        "icon": "shield",
        "severity_fn": lambda count: "LOW",
        "title_fn": lambda count: f"{count} demographic reference(s) identified by AI",
        "advice": [
            "Demographic data (nationality, ethnicity, religion) is legally protected in many countries.",
            "Avoid unnecessary collection or sharing of demographic data.",
            "Review GDPR/IT Act compliance if this data belongs to others.",
            "Remove demographic identifiers from documents where not required.",
        ],
    },
    # ── Phase 6: Vision Detection Types ────────────────────────────────
    "face_detected": {
        "category": "Human Face Detected in Image (Vision AI)",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"Face(s) detected in {count} image region(s) — biometric data at risk",
        "advice": [
            "Biometric facial data is highly sensitive and protected under GDPR, IT Act, and PDPB.",
            "Blur or redact all faces before sharing images publicly using the Blur Engine.",
            "Never upload unredacted photos containing faces to unencrypted cloud services.",
            "Obtain explicit consent before collecting or sharing images containing others' faces.",
            "Review photo sharing settings on all platforms where this image may have been uploaded.",
        ],
    },
    "id_card_visible": {
        "category": "Government ID Card Visible in Image (Vision AI)",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "HIGH",
        "title_fn": lambda count: f"ID document detected in image — immediate redaction required",
        "advice": [
            "Government ID cards (Aadhaar, PAN, Passport, DL) visible in images are a severe privacy risk.",
            "Use the Blur Engine to redact the entire ID card region before sharing.",
            "Never photograph government IDs and share the photos in chats or emails.",
            "If this image was shared, report potential identity theft to relevant authorities.",
            "Request deletion from any service or person you unintentionally shared this with.",
        ],
    },
    "document_type": {
        "category": "Sensitive Document Type Identified (Vision AI)",
        "icon": "shield",
        "severity_fn": lambda count: "MEDIUM",
        "title_fn": lambda count: f"Document classified as sensitive type by vision AI",
        "advice": [
            "The document type has been identified — ensure its contents are appropriately redacted.",
            "Sensitive documents (bank statements, medical records) should be encrypted at rest.",
            "Use secure file transfer methods (encrypted email, secure file share) when distributing.",
            "Audit who has access to this document type in your organization.",
        ],
    },
    "signature_visible": {
        "category": "Handwritten Signature Detected (Vision AI)",
        "icon": "shield",
        "severity_fn": lambda count: "MEDIUM",
        "title_fn": lambda count: f"Signature detected — can be used for forgery",
        "advice": [
            "Visible signatures in digital documents can be extracted and used for forgery.",
            "Redact signatures before sharing scanned documents publicly.",
            "Use digital signature solutions (DocuSign, Adobe Sign) instead of handwritten ones.",
            "Check if any document with your signature was shared without your consent.",
        ],
    },
    "qr_barcode": {
        "category": "QR Code / Barcode Detected (Vision AI)",
        "icon": "alert-triangle",
        "severity_fn": lambda count: "MEDIUM",
        "title_fn": lambda count: f"QR code or barcode detected — may contain embedded data",
        "advice": [
            "QR codes can embed URLs, personal data, payment info, or authentication tokens.",
            "Scan QR codes only with trusted apps before sharing documents containing them.",
            "If the QR code contains payment info or auth tokens, regenerate those credentials.",
            "Redact QR codes from documents before sharing if their contents are sensitive.",
        ],
    },
}


# ─── Main Generator ───────────────────────────────────────────────────────────

def generate_recommendations(
    emails: List[str],
    phones: List[str],
    passwords: List[str],
    score: float,
    risk_level: str,
    findings: List[dict] = None,
) -> List[dict]:
    """
    Generate actionable recommendations.
    If `findings` list is provided (Phase 3+), uses all 16 finding types.
    Otherwise falls back to the original email/phone/password approach.
    """
    recommendations = []
    seen_types = set()

    # ── Phase 3: Use full findings list if available ──────────────────────────
    if findings:
        # Group by type
        by_type: dict[str, list] = {}
        for f in findings:
            ftype = f.get("type", "")
            if ftype:
                by_type.setdefault(ftype, []).append(f.get("value", ""))

        # Generate rec for each detected type
        for ftype, items in by_type.items():
            advice_cfg = _TYPE_ADVICE.get(ftype)
            if not advice_cfg or not items:
                continue
            seen_types.add(ftype)
            count = len(items)
            severity = advice_cfg["severity_fn"](count)
            recommendations.append({
                "category": advice_cfg["category"],
                "severity": severity,
                "icon":     advice_cfg["icon"],
                "title":    advice_cfg["title_fn"](count),
                "advice":   advice_cfg["advice"],
            })

    else:
        # ── Fallback: original email/phone/password logic ─────────────────────
        if emails:
            cfg = _TYPE_ADVICE["email"]
            recommendations.append({
                "category": cfg["category"], "severity": cfg["severity_fn"](len(emails)),
                "icon": cfg["icon"], "title": cfg["title_fn"](len(emails)), "advice": cfg["advice"],
            })
        if phones:
            cfg = _TYPE_ADVICE["phone"]
            recommendations.append({
                "category": cfg["category"], "severity": cfg["severity_fn"](len(phones)),
                "icon": cfg["icon"], "title": cfg["title_fn"](len(phones)), "advice": cfg["advice"],
            })
        if passwords:
            cfg = _TYPE_ADVICE["password"]
            recommendations.append({
                "category": cfg["category"], "severity": cfg["severity_fn"](len(passwords)),
                "icon": cfg["icon"], "title": cfg["title_fn"](len(passwords)), "advice": cfg["advice"],
            })

    # ── General risk-level advice (always appended) ───────────────────────────
    if risk_level in ("CRITICAL", "HIGH"):
        recommendations.append({
            "category": "General High-Risk Alert",
            "severity": "HIGH",
            "icon": "alert-triangle",
            "title": "Your file contains highly sensitive data — act now",
            "advice": [
                "Do not share this file or its contents publicly.",
                "Delete any cloud copies of this file if it was unintentionally uploaded.",
                "Run a dark web scan at haveibeenpwned.com to check if your data has been breached.",
                "Consider filing a report with your country's data protection authority if data was leaked.",
                "Change all credentials found in this document immediately.",
            ],
        })
    elif risk_level == "MEDIUM":
        recommendations.append({
            "category": "General Medium-Risk Alert",
            "severity": "MEDIUM",
            "icon": "shield",
            "title": "Moderately sensitive data detected — review before sharing",
            "advice": [
                "Review the file carefully before sharing with others.",
                "Use the Blur Engine to redact sensitive information before distribution.",
                "Audit who currently has access to this type of document.",
            ],
        })
    else:
        recommendations.append({
            "category": "General Good Practice",
            "severity": "LOW",
            "icon": "check-circle",
            "title": "Low risk detected — great job!",
            "advice": [
                "Continue being mindful about what data appears in documents you share.",
                "Periodically scan important documents with this tool before sharing.",
                "Consider using file encryption for sensitive documents at rest.",
            ],
        })

    # Sort: HIGH → MEDIUM → LOW
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations.sort(key=lambda r: order.get(r["severity"], 3))

    return recommendations
