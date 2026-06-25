"""
Phase 16 — Remediation Auto-Generation Service
================================================
Per-finding step-by-step remediation checklists with:
- Clear, plain-language action steps
- Real working online tools only
- Urgency level (IMMEDIATE / WITHIN_24H / WITHIN_WEEK)
NO legal references — removed by user preference.
"""

from typing import List

# ── Remediation Database ──────────────────────────────────────────────────────
_REMEDIATION = {

    "aadhaar": {
        "urgency": "IMMEDIATE",
        "urgency_label": "Act within the next hour",
        "steps": [
            "Open the Blur Engine in this app and redact all Aadhaar numbers from the file.",
            "Delete the original unredacted file from your device and empty the recycle bin.",
            "If the file was shared via WhatsApp or email, message the recipients and ask them to delete it.",
            "If uploaded to Google Drive, Dropbox, or any cloud — delete it from there too.",
            "Log in to the UIDAI portal (uidai.gov.in) and check your Aadhaar usage history.",
            "Enable Aadhaar biometric lock at uidai.gov.in to prevent unauthorized authentication.",
            "In future, only share a masked Aadhaar (showing last 4 digits) — use the mAadhaar app.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
            {"name": "UIDAI Self Service Portal", "url": "https://myaadhaar.uidai.gov.in"},
            {"name": "UIDAI Lock/Unlock Biometrics", "url": "https://resident.uidai.gov.in/bio-lock"},
            {"name": "UIDAI Grievance Portal", "url": "https://grievances.uidai.gov.in"},
        ],
    },

    "pan_card": {
        "urgency": "IMMEDIATE",
        "urgency_label": "Act within 24 hours",
        "steps": [
            "Open the Blur Engine and redact the PAN number from the document right now.",
            "Delete all unredacted copies from your device, email drafts, and cloud storage.",
            "Check your CIBIL credit report for unauthorized loans or credit applications.",
            "Inform your bank that your PAN may have been exposed.",
            "If you suspect fraud, file a complaint at the Income Tax Department website.",
            "Report to the National Cybercrime Helpline if identity theft is suspected.",
            "In future, use a redacted copy showing only last 4 digits for KYC.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
            {"name": "CIBIL Credit Report (Free)", "url": "https://www.cibil.com/freecibilscore"},
            {"name": "Income Tax Complaints", "url": "https://www.incometax.gov.in/iec/foportal/help/contact-us"},
            {"name": "National Cybercrime Portal", "url": "https://cybercrime.gov.in"},
        ],
    },

    "credit_card": {
        "urgency": "IMMEDIATE",
        "urgency_label": "Call your bank RIGHT NOW",
        "steps": [
            "Call your bank's 24/7 helpline immediately and ask them to block the card.",
            "Request a replacement card with a new card number.",
            "Check your last 30 days of transactions online for anything suspicious.",
            "Dispute any unauthorized charges with your bank in writing or via their app.",
            "Turn on SMS and email alerts for all transactions on your new card.",
            "Use the Blur Engine to redact the card number from any documents.",
            "For online purchases, use your bank's virtual card number feature instead of the physical card.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
            {"name": "RBI Complaints Portal", "url": "https://cms.rbi.org.in"},
        ],
    },

    "cvv": {
        "urgency": "IMMEDIATE",
        "urgency_label": "Block your card within minutes",
        "steps": [
            "Call your bank right now — a CVV number can be used immediately for online fraud.",
            "Ask the bank to block the card and issue a replacement.",
            "Review all recent online transactions for anything you did not authorize.",
            "Raise a chargeback for any suspicious payments.",
            "Use the Blur Engine to remove the CVV from any documents.",
            "Set a transaction limit on your new card for extra safety.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
            {"name": "RBI Complaints Portal", "url": "https://cms.rbi.org.in"},
        ],
    },

    "password": {
        "urgency": "IMMEDIATE",
        "urgency_label": "Change passwords within the next hour",
        "steps": [
            "Find every account that uses this password and change it immediately.",
            "Use a strong, unique password for each account — at least 16 characters with symbols.",
            "Turn on two-factor authentication (2FA) on every affected account.",
            "Check haveibeenpwned.com to see if your email was in a known data breach.",
            "Install Bitwarden (free) to manage and generate strong passwords safely.",
            "Delete the file or note that had the password written in it.",
            "Never save passwords in plain text files, screenshots, or WhatsApp messages.",
        ],
        "tools": [
            {"name": "Have I Been Pwned", "url": "https://haveibeenpwned.com"},
            {"name": "Bitwarden (Free Password Manager)", "url": "https://bitwarden.com"},
            {"name": "Google Password Checkup", "url": "https://passwords.google.com"},
        ],
    },

    "email": {
        "urgency": "WITHIN_24H",
        "urgency_label": "Address within 24 hours",
        "steps": [
            "Go to haveibeenpwned.com and check if this email was in a known data breach.",
            "Enable 2FA on the email account using an authenticator app.",
            "Use the Blur Engine to redact the email address before resharing the document.",
            "If this email gets more spam after the exposure, set up strong spam filters.",
            "Consider using SimpleLogin or Apple Hide My Email to create alias emails for signups.",
            "Check your email account's recent login activity and log out unknown sessions.",
        ],
        "tools": [
            {"name": "Have I Been Pwned", "url": "https://haveibeenpwned.com"},
            {"name": "SimpleLogin (Email Aliases)", "url": "https://simplelogin.io"},
            {"name": "Blur Engine (this app)", "url": "/blur"},
        ],
    },

    "phone": {
        "urgency": "WITHIN_24H",
        "urgency_label": "Address within 24 hours",
        "steps": [
            "Register your number on the DND (Do Not Disturb) registry at trai.gov.in to stop spam calls.",
            "Call your mobile carrier and set a SIM lock PIN to prevent SIM swap attacks.",
            "Use the Blur Engine to redact your phone number from the document.",
            "Check which accounts are linked to this number — consider using a secondary number for less important services.",
            "Switch to an authenticator app for 2FA instead of SMS where possible.",
            "If you receive threatening or harassing calls, file a complaint at cybercrime.gov.in.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
            {"name": "TRAI DND Registry", "url": "https://sancharsaathi.gov.in/telecomUser/"},
            {"name": "National Cybercrime Portal", "url": "https://cybercrime.gov.in"},
        ],
    },

    "otp": {
        "urgency": "IMMEDIATE",
        "urgency_label": "Act now — OTP may still be valid",
        "steps": [
            "OTPs expire quickly — if this was just shared, assume it has been used already.",
            "Log in to the account the OTP was protecting and check recent activity right now.",
            "Change the password on that account immediately.",
            "Switch to an authenticator app (Google Authenticator or Authy) instead of SMS OTPs.",
            "Contact the service provider if you suspect unauthorized access.",
            "Delete the message or file that had the OTP.",
        ],
        "tools": [
            {"name": "Google Authenticator", "url": "https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2"},
            {"name": "Authy (2FA App)", "url": "https://authy.com"},
        ],
    },

    "dob": {
        "urgency": "WITHIN_WEEK",
        "urgency_label": "Address within this week",
        "steps": [
            "Remove your date of birth from any publicly shared documents.",
            "On social media (Facebook, Instagram, LinkedIn), hide your birth date from public view.",
            "Never share your DOB together with your name and address in the same document.",
            "Review accounts that use DOB as a security question — change to something harder to guess.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
        ],
    },

    "face_detected": {
        "urgency": "WITHIN_24H",
        "urgency_label": "Redact before sharing",
        "steps": [
            "Use the Blur Engine to blur all faces in the image before sharing it anywhere.",
            "Do not upload images with visible faces to public websites or cloud links.",
            "If you need to share the image, always blur the faces first.",
            "If the image was already shared publicly, request deletion from those platforms.",
            "On WhatsApp or social media, check who has access to this image and restrict it.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
        ],
    },

    "id_card_visible": {
        "urgency": "IMMEDIATE",
        "urgency_label": "Redact immediately",
        "steps": [
            "Open the Blur Engine right now and redact the entire ID card from the image.",
            "Delete all unredacted copies from your phone, computer, and cloud storage.",
            "If this image was sent to anyone, ask them to delete it immediately.",
            "Check with the issuing authority (UIDAI for Aadhaar, passport office, etc.) to confirm the ID is not misused.",
            "Never send photos of physical ID cards via WhatsApp or email — use official eKYC portals instead.",
        ],
        "tools": [
            {"name": "Blur Engine (this app)", "url": "/blur"},
            {"name": "National Cybercrime Portal", "url": "https://cybercrime.gov.in"},
            {"name": "UIDAI Grievance Portal", "url": "https://grievances.uidai.gov.in"},
        ],
    },
}

# Default for types without specific remediation
_DEFAULT_REMEDIATION = {
    "urgency": "WITHIN_WEEK",
    "urgency_label": "Review when possible",
    "steps": [
        "Review the detected data and decide if it needs to be redacted before sharing.",
        "Use the Blur Engine to remove or hide sensitive content.",
        "Avoid sharing documents with personal information unless absolutely necessary.",
        "Scan any important files with PrivacyShield before sending them to others.",
    ],
    "tools": [
        {"name": "Blur Engine (this app)", "url": "/blur"},
    ],
}

# ── Urgency order ─────────────────────────────────────────────────────────────
_URGENCY_ORDER = {"IMMEDIATE": 0, "WITHIN_24H": 1, "WITHIN_WEEK": 2}


def generate_remediation_plan(findings: List[dict], risk_level: str) -> dict:
    """
    Generate a full remediation plan from a list of findings.
    Returns structured remediation steps and tools per finding type.
    No legal references included.
    """
    # Group findings by type
    by_type: dict = {}
    for f in findings:
        ftype = f.get("type", "")
        if ftype:
            by_type.setdefault(ftype, []).append(f.get("value", ""))

    plans = []
    all_tools = {}

    for ftype, values in by_type.items():
        template = _REMEDIATION.get(ftype, _DEFAULT_REMEDIATION)
        plan = {
            "finding_type":  ftype,
            "count":         len(values),
            "urgency":       template["urgency"],
            "urgency_label": template["urgency_label"],
            "legal_refs":    [],          # always empty — removed by user preference
            "steps":         template["steps"],
            "tools":         template["tools"],
        }
        plans.append(plan)
        for tool in template["tools"]:
            all_tools[tool["name"]] = tool["url"]

    # Sort by urgency
    plans.sort(key=lambda p: _URGENCY_ORDER.get(p["urgency"], 3))

    # Summary stats
    immediate_count = sum(1 for p in plans if p["urgency"] == "IMMEDIATE")
    total_steps = sum(len(p["steps"]) for p in plans)

    return {
        "risk_level":        risk_level,
        "total_types":       len(plans),
        "immediate_actions": immediate_count,
        "total_steps":       total_steps,
        "plans":             plans,
        "all_tools":         [{"name": k, "url": v} for k, v in all_tools.items()],
        "legal_summary":     [],   # always empty — removed by user preference
    }
