"""
Phase 11 — Attack Simulation Engine
======================================
Simulates realistic cyberattack scenarios based on PII found across all
previous scan phases (file, URL, social, metadata). Shows the user EXACTLY
how an attacker could exploit their exposed data.

Simulation types:
  - phishing_email       → crafted email using name + email
  - sim_swap             → SIM-swap using phone
  - credential_stuffing  → password reuse attack using email + password
  - aadhaar_impersonation→ identity fraud using Aadhaar
  - gps_stalking         → physical tracking using GPS metadata
  - spear_phishing       → targeted attack using org + name + email
  - account_takeover     → MFA bypass using email + phone
  - data_broker_profile  → aggregated public profile from name + email + phone
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Attack Scenario Templates ─────────────────────────────────────────────────

SCENARIOS: list[dict] = [
    {
        "id":          "phishing_email",
        "name":        "Phishing Email Attack",
        "icon":        "mail",
        "severity":    "HIGH",
        "color":       "#ef4444",
        "requires":    ["email"],
        "optional":    ["person_name", "organization"],
        "description": "Attacker crafts a personalised phishing email to steal credentials or install malware.",
        "steps": [
            "Attacker collects your exposed email address from a public source.",
            "Attacker spoofs a trusted sender (bank, employer, government).",
            "A convincing email is sent with a malicious link or attachment.",
            "Victim clicks the link → credentials captured on a fake login page.",
            "Attacker gains full account access within minutes.",
        ],
        "mitigations": [
            "Enable spam/phishing filters (Google Advanced Protection, Microsoft Defender).",
            "Never click email links — always navigate directly to websites.",
            "Use a unique masked email per service (Apple Hide My Email, SimpleLogin).",
            "Enable two-factor authentication on all accounts.",
        ],
    },
    {
        "id":          "sim_swap",
        "name":        "SIM-Swap Attack",
        "icon":        "phone",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["phone"],
        "optional":    ["person_name", "aadhaar"],
        "description": "Attacker convinces your carrier to transfer your number to their SIM, bypassing SMS-based 2FA.",
        "steps": [
            "Attacker obtains your phone number from exposed data.",
            "Attacker calls your mobile carrier, pretending to be you.",
            "Using your leaked name/ID, they pass identity verification.",
            "Your number is ported to the attacker's SIM card.",
            "Attacker receives all your SMS codes, gains access to bank/email accounts.",
        ],
        "mitigations": [
            "Set a carrier account PIN that is required for any SIM changes.",
            "Switch from SMS-based 2FA to an authenticator app (Google Authenticator, Authy).",
            "Use a hardware security key (YubiKey) for critical accounts.",
            "Never share your phone number publicly.",
        ],
    },
    {
        "id":          "credential_stuffing",
        "name":        "Credential Stuffing",
        "icon":        "key",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["email", "password"],
        "optional":    [],
        "description": "Attacker uses your leaked email+password combination across thousands of websites automatically.",
        "steps": [
            "Attacker downloads a breach database containing your email and password.",
            "Automated bots test the combo across 100+ popular sites simultaneously.",
            "Any site where you reused the password is compromised within hours.",
            "Attacker sells access to compromised accounts on dark web markets.",
            "Bank, social media, and shopping accounts are all at risk.",
        ],
        "mitigations": [
            "Change the exposed password IMMEDIATELY on every account that uses it.",
            "Use a password manager (Bitwarden, 1Password) with unique passwords per site.",
            "Enable two-factor authentication everywhere.",
            "Check haveibeenpwned.com to see all breach exposures for your email.",
        ],
    },
    {
        "id":          "aadhaar_impersonation",
        "name":        "Aadhaar Identity Fraud",
        "icon":        "shield",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["aadhaar"],
        "optional":    ["person_name", "phone"],
        "description": "Attacker uses your Aadhaar number to impersonate you for financial fraud, SIM acquisition, or government services.",
        "steps": [
            "Attacker obtains your 12-digit Aadhaar number from exposed document.",
            "Combines with any available name/DOB/phone to build a complete profile.",
            "Uses your Aadhaar to open bank accounts, get loans, or obtain SIMs.",
            "Fraud is conducted under your identity — you bear the liability.",
            "Reversing Aadhaar-based fraud takes months of legal proceedings.",
        ],
        "mitigations": [
            "Lock your Aadhaar biometric data at myaadhaar.uidai.gov.in immediately.",
            "Generate a Virtual ID (VID) to share instead of your actual Aadhaar number.",
            "Never share your Aadhaar in plain text documents or screenshots.",
            "Report exposure to UIDAI helpline: 1947.",
            "Monitor your CIBIL/credit score for unauthorised loan applications.",
        ],
    },
    {
        "id":          "gps_stalking",
        "name":        "GPS Location Tracking / Stalking",
        "icon":        "map-pin",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["gps_latitude"],
        "optional":    ["gps_longitude", "gps_full"],
        "description": "GPS coordinates embedded in your photos reveal your home, workplace, or daily routes to anyone who downloads them.",
        "steps": [
            "Attacker downloads an image you shared publicly (social media, cloud, email).",
            "Reads GPS EXIF data embedded in the image — shows exact coordinates.",
            "Plots your location on Google Maps → sees your home or workplace.",
            "Over multiple photos, attacker maps your daily routine and movements.",
            "Physical surveillance, stalking, or targeted robbery becomes possible.",
        ],
        "mitigations": [
            "Disable camera GPS / location tagging in your phone settings NOW.",
            "Strip EXIF data from all photos before sharing (use ExifTool or online EXIF removers).",
            "Review all previously shared photos and request deletion where possible.",
            "Use the Metadata Scanner to check every photo before uploading.",
            "Never share unprocessed photos from personal devices publicly.",
        ],
    },
    {
        "id":          "spear_phishing",
        "name":        "Spear Phishing (Targeted)",
        "icon":        "target",
        "severity":    "HIGH",
        "color":       "#ef4444",
        "requires":    ["email", "person_name"],
        "optional":    ["organization"],
        "description": "Attacker uses your name, organisation, and email to craft a highly personalised deceptive message that bypasses generic spam filters.",
        "steps": [
            "Attacker aggregates: your name, email, employer, and role.",
            "Crafts a message that appears to come from your IT team, bank, or manager.",
            "Email references real projects, colleagues, or events to appear legitimate.",
            "You open the attachment / click the link — malware installs silently.",
            "Attacker gains access to your corporate network or personal accounts.",
        ],
        "mitigations": [
            "Verify any unexpected requests by calling the sender on a known number.",
            "Be suspicious of urgency — 'Act now!' is a social engineering red flag.",
            "Use email authentication (DMARC, SPF, DKIM) to verify sender identity.",
            "Keep your professional information minimal on public platforms.",
        ],
    },
    {
        "id":          "account_takeover",
        "name":        "Account Takeover via SMS Intercept",
        "icon":        "lock",
        "severity":    "HIGH",
        "color":       "#ef4444",
        "requires":    ["email", "phone"],
        "optional":    [],
        "description": "With both your email and phone number, attacker can trigger password resets and intercept SMS OTPs to take over accounts.",
        "steps": [
            "Attacker initiates 'Forgot Password' on your email or bank using your email address.",
            "Reset link / OTP is sent to your phone number.",
            "Attacker intercepts SMS via SS7 vulnerability or SIM-swap (if prior attack succeeded).",
            "Password is reset — attacker owns the account.",
            "All accounts linked to that email are now compromised.",
        ],
        "mitigations": [
            "Switch all accounts from SMS OTP to an authenticator app.",
            "Use a hardware security key as your primary 2FA method.",
            "Set up account recovery codes and store them offline.",
            "Enable login alerts for every important account.",
        ],
    },
    {
        "id":          "data_broker_profile",
        "name":        "Data Broker Aggregation Profile",
        "icon":        "database",
        "severity":    "MEDIUM",
        "color":       "#f59e0b",
        "requires":    ["person_name"],
        "optional":    ["email", "phone", "organization"],
        "description": "Data brokers combine your leaked information with public records to build a comprehensive profile that is sold to advertisers, scammers, and anyone willing to pay.",
        "steps": [
            "Your name, email, phone, and employer are scraped from multiple sources.",
            "Data broker aggregates with voter records, property records, and social profiles.",
            "A complete dossier — address history, family members, income estimate — is created.",
            "This profile is sold to cold-callers, scammers, and targeted advertisers.",
            "Competitors, stalkers, or hostile parties can purchase your full profile for <$10.",
        ],
        "mitigations": [
            "Submit opt-out requests to major data brokers: Spokeo, Whitepages, BeenVerified.",
            "Use a service like DeleteMe or Incogni to automate broker opt-outs.",
            "Use a PO Box or virtual address instead of your home address online.",
            "Minimise your digital footprint — remove old accounts and unused profiles.",
        ],
    },
    {
        "id":          "pan_financial_fraud",
        "name":        "PAN Card Financial Fraud",
        "icon":        "credit-card",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["pan_card"],
        "optional":    ["person_name", "phone"],
        "description": "Your PAN number can be used to file fraudulent tax returns, open investment accounts, or take out credit in your name.",
        "steps": [
            "Attacker obtains your PAN number from a leaked document or screenshot.",
            "Files a fraudulent income tax return to claim your refund.",
            "Opens demat/trading accounts under your PAN without your knowledge.",
            "Takes out personal loans — your CIBIL score is damaged.",
            "Income Tax Department notices may come to your address months later.",
        ],
        "mitigations": [
            "Check your ITR status regularly at incometax.gov.in.",
            "Monitor your CIBIL credit report every 3 months for unknown accounts.",
            "Never share your PAN in plaintext — use only via secure government portals.",
            "Report PAN misuse to the Income Tax Department immediately.",
        ],
    },
    {
        "id":          "cvv_card_fraud",
        "name":        "Complete Card Fraud (Card + CVV)",
        "icon":        "credit-card",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["credit_card", "cvv"],
        "optional":    ["person_name"],
        "description": "With both your card number and CVV exposed, an attacker has everything needed to make instant online purchases — no physical card required.",
        "steps": [
            "Attacker captures both your card number and CVV from a document or screenshot.",
            "Card number + CVV is the complete 'card-not-present' package for online fraud.",
            "Immediately tests on sites that don't require 3D-Secure (many international sites).",
            "Bulk purchases, gift cards, or wallet top-ups are made before your bank flags it.",
            "Card is sold on dark-web carding forums for $20-$80 while fraud continues.",
        ],
        "mitigations": [
            "Call your bank IMMEDIATELY and report the card as compromised — get a new card issued.",
            "Set up real-time transaction alerts via your banking app.",
            "Enable 3D-Secure/OTP verification for all online transactions.",
            "Never photograph or scan payment cards — the CVV is the most sensitive element.",
        ],
    },
    {
        "id":          "otp_account_takeover",
        "name":        "Live OTP Exposed — Immediate Account Access",
        "icon":        "zap",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["otp"],
        "optional":    ["phone", "email"],
        "description": "An OTP (One-Time Password) visible in a screenshot or document is valid for 30-300 seconds. An attacker who sees it has real-time access to your account RIGHT NOW.",
        "steps": [
            "Your OTP was captured in a screenshot or photo while it was still active.",
            "OTPs are time-sensitive — attacker must act within 30 to 300 seconds.",
            "If screenshot was shared publicly (WhatsApp, social), attacker grabs it instantly.",
            "Attacker enters the OTP on the target login page — gains full account access.",
            "Your account password is then changed, locking you out permanently.",
        ],
        "mitigations": [
            "NEVER share screenshots of OTP messages — even with people you trust.",
            "If an OTP screenshot was shared, immediately change your account password.",
            "Enable app-based 2FA (Google Authenticator) instead of SMS OTP where possible.",
            "Check if any new devices were added to your account and remove them.",
        ],
    },
    {
        "id":          "id_document_impersonation",
        "name":        "ID Document Exposure — Identity Fraud",
        "icon":        "badge",
        "severity":    "CRITICAL",
        "color":       "#dc2626",
        "requires":    ["id_card_visible"],
        "optional":    ["id_number", "person_name"],
        "description": "A scanned or photographed identity document (passport, driving license, voter ID) gives an attacker enough information to impersonate you in person or at government services.",
        "steps": [
            "Attacker obtains your scanned ID card image from the file.",
            "Reads your full name, DOB, ID number, and address from the document.",
            "Creates a colour photocopy or digital replica for physical use.",
            "Uses the ID at a telecom store to obtain a new SIM card in your name.",
            "Uses the ID at a bank branch or NBFC to apply for a loan under your identity.",
        ],
        "mitigations": [
            "Never send clear photos of your ID documents over messaging apps.",
            "Always watermark ID copies with the purpose and date (e.g., 'For Airtel SIM - June 2025').",
            "File a police complaint if your ID document image has been leaked.",
            "Alert your bank and telecom provider that your ID has been compromised.",
        ],
    },
    {
        "id":          "face_spoofing",
        "name":        "Face Spoofing / Deepfake Identity Attack",
        "icon":        "scan-face",
        "severity":    "HIGH",
        "color":       "#ef4444",
        "requires":    ["face_detected"],
        "optional":    ["person_name", "id_card_visible"],
        "description": "Your face is visible in this file. Facial images are used for biometric verification, deepfake generation, and social engineering attacks targeting your contacts.",
        "steps": [
            "Attacker extracts your clear facial image from the file.",
            "Runs it through free deepfake tools (DeepFaceLab, FaceSwap) to create fake video.",
            "Uses the deepfake in a WhatsApp/video call to impersonate you to family or colleagues.",
            "Creates fake social media profiles with your face to deceive your contacts.",
            "Some banks and apps use face-based KYC — a high-quality photo can bypass weaker checks.",
        ],
        "mitigations": [
            "Remove or blur your face from any document or image before sharing.",
            "Enable enhanced biometric liveness detection on banking apps where available.",
            "Alert your contacts if your photo has been leaked — warn them of potential impersonation.",
            "Report fake profiles using your image to the platform immediately.",
        ],
    },
    {
        "id":          "qr_exploitation",
        "name":        "QR Code Exploitation",
        "icon":        "qr-code",
        "severity":    "HIGH",
        "color":       "#ef4444",
        "requires":    ["qr_barcode"],
        "optional":    ["person_name"],
        "description": "A QR code found in your file could encode a UPI payment link, malicious URL, contact data, or authentication token that can be exploited by anyone who scans it.",
        "steps": [
            "Attacker scans or decodes the QR code found in the document/image.",
            "If it is a UPI QR: attacker requests payment from anyone they show it to.",
            "If it is a URL: attacker checks if it links to login tokens or private resources.",
            "If it is a vCard/contact: attacker harvests your personal details.",
            "QR codes in banking apps sometimes encode one-time authentication tokens.",
        ],
        "mitigations": [
            "Never share QR codes generated for payments — they encode your UPI ID and can be misused.",
            "Regenerate any payment QR codes that were exposed.",
            "Check what the QR encodes using a QR decoder app before sharing any document containing one.",
            "Invalidate any authentication QR (e.g. WhatsApp Web QR) that was captured in a screenshot.",
        ],
    },
    {
        "id":          "signature_forgery",
        "name":        "Signature Forgery / Document Tampering",
        "icon":        "pen-line",
        "severity":    "MEDIUM",
        "color":       "#f59e0b",
        "requires":    ["signature_visible"],
        "optional":    ["person_name", "id_card_visible"],
        "description": "A visible handwritten signature in your document can be digitally extracted and used to forge contracts, cheques, or official documents bearing your name.",
        "steps": [
            "Attacker captures the clear image of your handwritten signature.",
            "Digitally isolates the signature from the document background.",
            "Pastes it onto contracts, cheques, or legal letters.",
            "Forged cheques may clear at branches with lax verification.",
            "Forged contracts used in real estate or financial disputes under your name.",
        ],
        "mitigations": [
            "Never send unredacted copies of signed documents — cover the signature unless necessary.",
            "Use digital signatures (DSC / Aadhaar e-Sign) instead of handwritten where possible.",
            "Add a watermark over your physical signature on digital copies.",
            "Alert your bank if a signed cheque image has been leaked.",
        ],
    },
    {
        "id":          "social_profile_attack",
        "name":        "Social Profile Exploitation",
        "icon":        "user-search",
        "severity":    "MEDIUM",
        "color":       "#f59e0b",
        "requires":    ["username"],
        "optional":    ["display_name", "bio", "location", "website"],
        "description": "Your public social media handle, combined with your bio and linked details, enables attackers to cross-reference your identity across platforms and launch targeted social engineering.",
        "steps": [
            "Attacker has your username from the scanned social media data.",
            "Searches the same username across Instagram, Twitter, LinkedIn, and Reddit.",
            "Aggregates your bio, posts, photos, and follower list from all platforms.",
            "Builds a complete profile of your interests, routine, and social connections.",
            "Uses this to craft convincing impersonation or phishing messages to your connections.",
        ],
        "mitigations": [
            "Use different usernames on different platforms to prevent cross-platform tracking.",
            "Set your social media profiles to private.",
            "Remove your real name, location, and workplace from public social profiles.",
            "Regularly audit what information is visible to non-followers.",
        ],
    },
    {
        "id":          "http_mitm",
        "name":        "Man-in-the-Middle Interception (HTTP Site)",
        "icon":        "wifi",
        "severity":    "MEDIUM",
        "color":       "#f59e0b",
        "requires":    ["http_only"],
        "optional":    ["email", "password"],
        "description": "The scanned URL uses plain HTTP (not HTTPS). Any data you submit on this site — logins, forms, personal info — is transmitted in plaintext and can be intercepted on the same network.",
        "steps": [
            "Attacker positions themselves on the same Wi-Fi network as you.",
            "Uses ARP spoofing or a rogue hotspot to intercept your traffic.",
            "All HTTP data flows in plaintext — the attacker reads everything you submit.",
            "Captures login credentials, form data, and session cookies in real time.",
            "Uses captured session cookie to hijack your authenticated session immediately.",
        ],
        "mitigations": [
            "Never submit personal information on HTTP (non-HTTPS) websites.",
            "Use a VPN when on public Wi-Fi to encrypt all traffic.",
            "Look for the padlock icon and 'https://' in the URL before submitting any data.",
            "Report HTTP-only sites that handle personal data as a security vulnerability.",
        ],
    },
    {
        'id':          'exposed_password',
        'name':        'Exposed Password - Direct Account Compromise',
        'icon':        'key',
        'severity':    'CRITICAL',
        'color':       '#dc2626',
        'requires':    ['password'],
        'optional':    ['email', 'person_name'],
        'description': 'A plaintext password was found in your file or screenshot. Anyone with access can immediately use it.',
        'steps': [
            'Your password was captured in plaintext in a screenshot or document.',
            'Attacker searches for associated email/username using your name.',
            'Tries the leaked password on email, banking, and social media platforms.',
            'If the same password is reused across sites, all those accounts are at risk.',
            'Attacker enables their own 2FA, locking you out permanently.',
        ],
        'mitigations': [
            'Change this password IMMEDIATELY on every account that uses it.',
            'Never type passwords in documents or take screenshots of passwords.',
            'Use a password manager (Bitwarden, 1Password) with unique passwords.',
            'Enable two-factor authentication on all important accounts.',
            'Check haveibeenpwned.com to see if this password is in known breaches.',
        ],
    },
    {
        'id':          'password_reuse',
        'name':        'Password Reuse Attack',
        'icon':        'refresh-cw',
        'severity':    'HIGH',
        'color':       '#ef4444',
        'requires':    ['password'],
        'optional':    ['email'],
        'description': 'An exposed password is tested across hundreds of platforms automatically, compromising every account that reuses it.',
        'steps': [
            'Attacker captures the exposed password from your file or screenshot.',
            'Feeds the password into automated credential stuffing tools.',
            'Bot tests the password across 500+ popular websites within minutes.',
            'Matches are found wherever you reused the same password.',
            'Attacker silently accesses those accounts without you knowing.',
        ],
        'mitigations': [
            'Treat every site where you used this password as potentially compromised.',
            'Generate unique passwords for every service using a password manager.',
            'Run a breach check at haveibeenpwned.com/passwords for this password.',
            'Switch to passkeys where supported for passwordless security.',
        ],
    },
]


# ── Mapping: finding types → what we extract for simulation ──────────────────

_TYPE_MAP = {
    "email":           "email",
    "phone":           "phone",
    "password":        "password",
    "aadhaar":         "aadhaar",
    "pan_card":        "pan_card",
    "credit_card":     "credit_card",
    "cvv":             "cvv",            # card security code
    "otp":             "otp",            # one-time password (live session risk)
    "id_number":       "id_number",      # passport / DL / any govt ID number
    "person_name":     "person_name",
    "location":        "location",
    "organization":    "organization",
    "gps_latitude":    "gps_latitude",
    "gps_longitude":   "gps_longitude",
    "gps_full":        "gps_full",
    "face_detected":   "face_detected",     # vision finding
    "id_card_visible": "id_card_visible",   # vision finding
    "signature_visible":"signature_visible", # vision finding
    "qr_barcode":      "qr_barcode",         # vision / QR scan
    "username":        "username",           # social profile handle
    "display_name":    "person_name",        # social real name → person_name
    "http_only":       "http_only",          # URL scan security finding
    # Metadata aliases → person_name / organization
    "author":          "person_name",
    "creator":         "person_name",
    "last_modified_by":"person_name",
    "company":         "organization",
    "artist":          "person_name",
}


# ── Main engine ───────────────────────────────────────────────────────────────

def run_attack_simulation(
    findings: list[dict],
    score: float = 0.0,
    risk_level: str = "SAFE",
    source: str = "file",
) -> dict:
    """
    Given a list of finding dicts (each with 'type' and 'value'),
    determine which attack scenarios apply and build simulation results.

    Returns:
      {
        applicable_attacks: [ {scenario + demo fields}, ... ],
        total_attacks: int,
        highest_severity: str,
        overall_threat_score: float,    # 0-100
        pii_map: { type: [values] },
      }
    """
    # Build a PII map: type → list of values
    pii_map: dict[str, list[str]] = {}
    for f in findings:
        ftype = _TYPE_MAP.get(f.get("type", ""), f.get("type", ""))
        val   = str(f.get("value", "")).strip()
        if ftype and val:
            pii_map.setdefault(ftype, [])
            if val not in pii_map[ftype]:
                pii_map[ftype].append(val)

    applicable = []
    severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

    for sc in SCENARIOS:
        # Check all required fields are present
        if not all(req in pii_map for req in sc["requires"]):
            continue

        # Build demo/preview values for this scenario
        demo = _build_demo(sc, pii_map)
        applicable.append({
            "id":          sc["id"],
            "name":        sc["name"],
            "icon":        sc["icon"],
            "severity":    sc["severity"],
            "color":       sc["color"],
            "description": sc["description"],
            "steps":       sc["steps"],
            "mitigations": sc["mitigations"],
            "demo":        demo,
            "confidence":  _calc_confidence(sc, pii_map),
        })

    # Add dynamic scenarios for PII combos not covered by static list
    dynamic = _build_dynamic_scenarios(pii_map, {a["id"] for a in applicable})
    applicable.extend(dynamic)

    # Sort: CRITICAL → HIGH → MEDIUM
    applicable.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)

    # Overall threat score
    if applicable:
        base = score
        attack_boost = sum({"CRITICAL":15, "HIGH":8, "MEDIUM":4}.get(a["severity"],0) for a in applicable)
        threat_score = min(base + attack_boost, 100.0)
    else:
        threat_score = score * 0.5

    highest = applicable[0]["severity"] if applicable else "SAFE"

    return {
        "applicable_attacks":   applicable,
        "total_attacks":        len(applicable),
        "highest_severity":     highest,
        "overall_threat_score": round(threat_score, 1),
        "pii_map":              {k: v[:3] for k, v in pii_map.items()},  # cap values for safety
        "source":               source,
        "base_score":           score,
        "base_risk":            risk_level,
    }


def _build_demo(scenario: dict, pii_map: dict) -> dict:
    """Build a realistic-looking attack demo/preview using actual leaked values."""
    demo = {}
    name  = (pii_map.get("person_name", ["[Your Name]"])[0])
    email = (pii_map.get("email",  ["victim@example.com"])[0])
    phone = (pii_map.get("phone",  ["98XXXXXXXX"])[0])
    org   = (pii_map.get("organization", ["Your Organisation"])[0])

    sid = scenario["id"]

    if sid == "phishing_email":
        demo["email_preview"] = (
            f"From: security@{org.lower().replace(' ','')+'.com' if 'org' in pii_map else 'bank-alerts.com'}\n"
            f"To: {email}\n"
            f"Subject: URGENT: Your account requires immediate verification\n\n"
            f"Dear {name},\n\n"
            f"We have detected unusual activity on your account. Click the link below\n"
            f"within 24 hours to verify your identity and avoid suspension:\n\n"
            f"  → http://secure-verify-{email.split('@')[0]}.malicious-site.xyz/login\n\n"
            f"This message was automatically generated for {email}.\n"
            f"Do not reply to this email."
        )

    elif sid == "sim_swap":
        demo["call_script"] = (
            f"Attacker → Carrier: 'Hi, I need to transfer my SIM to a new phone.'\n"
            f"Carrier: 'Can you verify your name and number?'\n"
            f"Attacker: 'My name is {name}, number {phone}.'\n"
            f"Carrier: 'Can you confirm your last 4 digits of Aadhaar?'\n"
            f"Attacker: '{pii_map.get('aadhaar',['XXXX'])[0][-4:] if 'aadhaar' in pii_map else 'XXXX'}'\n"
            f"Carrier: 'Transfer approved. New SIM activated.'\n"
            f"→ Attacker now receives all SMS OTPs sent to {phone}."
        )

    elif sid == "credential_stuffing":
        pw = pii_map.get("password", ["[exposed_password]"])[0]
        demo["attack_preview"] = (
            f"Leaked combo: {email} / {pw}\n\n"
            f"Automated bot testing across 200+ sites:\n"
            f"  gmail.com          → TRYING...\n"
            f"  facebook.com       → TRYING...\n"
            f"  amazon.in          → SUCCESS (same password reused!)\n"
            f"  netbanking.sbi.in  → TRYING...\n"
            f"  flipkart.com       → SUCCESS (same password reused!)\n\n"
            f"Result: {email} compromised on 2+ sites within 4 minutes."
        )

    elif sid == "aadhaar_impersonation":
        aadhaar = pii_map.get("aadhaar", ["XXXX XXXX XXXX"])[0]
        demo["fraud_preview"] = (
            f"Leaked Aadhaar: {aadhaar}\n\n"
            f"Attacker actions:\n"
            f"  1. Gets a new SIM using Aadhaar-based e-KYC\n"
            f"  2. Opens a Jan Dhan bank account in your name\n"
            f"  3. Applies for a ₹50,000 personal loan\n"
            f"  4. Account flagged — YOUR CIBIL score drops 150 points\n"
            f"  5. RBI complaint filed months later under your name."
        )

    elif sid == "gps_stalking":
        gps = pii_map.get("gps_full", pii_map.get("gps_latitude", ["?"]))[0]
        demo["location_preview"] = (
            f"GPS found in photo EXIF: {gps}\n\n"
            f"Google Maps link: https://maps.google.com/?q={gps.replace(', ',',')}\n\n"
            f"What attacker sees:\n"
            f"  → Exact location where photo was taken\n"
            f"  → Cross-referenced with 3 other shared photos → your home address\n"
            f"  → Daily routine mapped over 7 days of shared images\n"
            f"  → Physical surveillance possible with this information."
        )

    elif sid == "spear_phishing":
        demo["email_preview"] = (
            f"From: it-support@{org.lower().replace(' ','')}.com\n"
            f"To: {email}\n"
            f"Subject: Action required: Password expiry for {name}\n\n"
            f"Hi {name},\n\n"
            f"Your {org} account password expires in 2 hours.\n"
            f"Please update it immediately to avoid losing access:\n\n"
            f"  → https://{org.lower().replace(' ','')}-portal.phishingsite.xyz\n\n"
            f"IT Help Desk | {org}"
        )

    elif sid == "account_takeover":
        demo["attack_preview"] = (
            f"Step 1: Attacker visits gmail.com → 'Forgot password?'\n"
            f"        Enters: {email}\n\n"
            f"Step 2: Google sends OTP to {phone}\n\n"
            f"Step 3: Attacker intercepts OTP via SS7 exploit\n"
            f"        (Telco-level vulnerability — no app needed)\n\n"
            f"Step 4: New password set. Account hijacked.\n"
            f"        All emails, contacts, and Drive files now accessible.\n\n"
            f"Time taken: ~8 minutes."
        )

    elif sid == "data_broker_profile":
        demo["profile_preview"] = (
            f"Name:         {name}\n"
            f"Email:        {email}\n"
            f"Phone:        {phone}\n"
            f"Employer:     {org}\n"
            f"Address:      [Aggregated from public records]\n"
            f"Family:       [Relatives found via social graph]\n"
            f"Income est.:  [Inferred from employer/location]\n"
            f"Available on: Spokeo, BeenVerified, Whitepages, Pipl\n"
            f"Sale price:   $2.99 — $9.99 per report\n\n"
            f"This profile was built entirely from publicly available data."
        )

    elif sid == "pan_financial_fraud":
        pan = pii_map.get("pan_card", ["ABCDE1234F"])[0]
        demo["fraud_preview"] = (
            f"Leaked PAN: {pan}\n\n"
            f"Attacker actions:\n"
            f"  1. Files ITR for AY 2024-25 claiming ₹80,000 refund\n"
            f"  2. Opens demat account at a discount broker\n"
            f"  3. Applies for credit card — limit approved ₹1,50,000\n"
            f"  4. Your CIBIL score drops; IT Dept sends notice to your address\n"
            f"  5. Takes 6-18 months of legal battle to resolve."
        )

    elif sid == 'exposed_password':
        pw = pii_map.get('password', ['[exposed_password]'])[0]
        masked_pw = (pw[:2] + '*' * (len(pw) - 2)) if len(pw) > 2 else '**'
        demo['attack_preview'] = (
            f'Password found in plaintext: {masked_pw}\n\n'
            f'Attacker tests this password on:\n'
            f'  gmail.com          -> TRYING...\n'
            f'  instagram.com      -> TRYING...\n'
            f'  amazon.in          -> SUCCESS (password matched!)\n'
            f'  netbanking.sbi.in  -> TRYING...\n'
            f'  facebook.com       -> SUCCESS (password matched!)\n\n'
            f'Result: 2 accounts compromised within 3 minutes of finding the screenshot.'
        )

    elif sid == 'password_reuse':
        pw = pii_map.get('password', ['[exposed_password]'])[0]
        masked = pw[:2] + '*' * (len(pw) - 2) if len(pw) > 2 else '**'
        demo['attack_preview'] = (
            f'Exposed password: {masked}\n\n'
            f'Automated reuse check (credential stuffing bot):\n'
            f'  google.com      -> Testing... match found\n'
            f'  linkedin.com    -> Testing... match found\n'
            f'  flipkart.com    -> Testing... no match\n'
            f'  paytm.com       -> Testing... match found\n\n'
            f'3 accounts breached. Attacker logs in silently and enables their own 2FA,\n'
            f'locking you out permanently within minutes.'
        )


    elif sid == "cvv_card_fraud":
        card = pii_map.get("credit_card", ["XXXX XXXX XXXX XXXX"])[0]
        cvv  = pii_map.get("cvv", ["XXX"])[0]
        demo["attack_preview"] = (
            f"Card data captured:\n"
            f"  Card: {card[:4]} **** **** ****\n"
            f"  CVV:  {cvv}\n\n"
            f"Attacker attempts (card-not-present):\n"
            f"  aliexpress.com    -> SUCCESS (no 3DS required)\n"
            f"  amazon.com (US)   -> SUCCESS\n"
            f"  steamgames.com    -> BLOCKED (3DS required)\n"
            f"  recharge sites    -> SUCCESS\n\n"
            f"Estimated fraud within 10 minutes: ₹8,000 – ₹25,000"
        )

    elif sid == "otp_account_takeover":
        otp = pii_map.get("otp", ["XXXXXX"])[0]
        demo["attack_preview"] = (
            f"OTP captured: {otp}\n\n"
            f"Attacker actions (time-critical — within 60 seconds):\n"
            f"  1. Initiates login on target account\n"
            f"  2. Enters OTP: {otp}\n"
            f"  3. Access granted — changes password immediately\n"
            f"  4. Adds new recovery phone number\n"
            f"  5. You are locked out permanently.\n\n"
            f"Time from OTP capture to account lockout: ~45 seconds."
        )

    elif sid == "id_document_impersonation":
        name = pii_map.get("person_name", ["[Your Name]"])[0]
        demo["attack_preview"] = (
            f"ID document image captured.\n\n"
            f"Attacker can now:\n"
            f"  1. Print a colour copy of your ID\n"
            f"  2. Walk into a Jio/Airtel store → obtain SIM in your name\n"
            f"  3. Visit NBFC → apply for instant personal loan\n"
            f"  4. Register a company with your ID at the ROC\n\n"
            f"Identity of: {name}\n"
            f"All above actions are possible with ONE clear ID photo."
        )

    elif sid == "face_spoofing":
        name = pii_map.get("person_name", ["[Your Name]"])[0]
        demo["attack_preview"] = (
            f"Face detected in file. Target: {name}\n\n"
            f"Attacker workflow:\n"
            f"  1. Extracts face from image (auto-cropped)\n"
            f"  2. Runs through DeepFaceLab → generates 30-second deepfake video\n"
            f"  3. Sends WhatsApp video call to {name}'s contacts:\n"
            f"     'Hi, it's me. I'm in trouble, please send money urgently.'\n"
            f"  4. Creates Instagram clone account with your photos\n"
            f"  5. Messages your followers with scam links.\n\n"
            f"Deepfake creation time: ~15 minutes with consumer GPU."
        )

    elif sid == "qr_exploitation":
        qr_val = pii_map.get("qr_barcode", ["[QR content]"])[0]
        preview = qr_val[:60] + ("..." if len(qr_val) > 60 else "")
        demo["attack_preview"] = (
            f"QR code decoded: {preview}\n\n"
            f"Risk analysis:\n"
            f"  - If UPI link: attacker requests payments using your QR\n"
            f"  - If URL: attacker checks for auth tokens or private data\n"
            f"  - If vCard: harvests your contact details automatically\n"
            f"  - If session token: provides direct account access\n\n"
            f"Anyone who scans this QR can immediately exploit its content."
        )

    elif sid == "signature_forgery":
        name = pii_map.get("person_name", ["[Your Name]"])[0]
        demo["attack_preview"] = (
            f"Handwritten signature of {name} detected.\n\n"
            f"Forgery risk:\n"
            f"  1. Signature digitally extracted from document background\n"
            f"  2. Pasted onto a blank cheque template\n"
            f"  3. Presented at a bank branch for encashment\n"
            f"  4. Used on a forged property agreement or loan guarantee\n\n"
            f"A clear signature image is sufficient for basic forgery attempts."
        )

    elif sid == "social_profile_attack":
        username = pii_map.get("username", ["[username]"])[0]
        demo["attack_preview"] = (
            f"Social handle found: @{username}\n\n"
            f"Cross-platform search results:\n"
            f"  Instagram  -> @{username} found (public profile)\n"
            f"  Twitter/X  -> @{username} found (3,200 posts indexed)\n"
            f"  LinkedIn   -> Profile matched by name\n\n"
            f"Attacker aggregates: photos, location, employer, daily posts.\n"
            f"Profile sold for $1.50 or used directly for targeted scam."
        )

    elif sid == "http_mitm":
        demo["attack_preview"] = (
            f"HTTP (unencrypted) URL detected in scan.\n\n"
            f"Network interception demo:\n"
            f"  Attacker creates rogue Wi-Fi: 'Free Airport WiFi'\n"
            f"  You connect and visit the HTTP site\n"
            f"  Attacker's tool captures raw HTTP traffic:\n\n"
            f"  POST /login HTTP/1.1\n"
            f"  Content-Type: application/x-www-form-urlencoded\n"
            f"  username=you%40email.com&password=YourPassword123\n\n"
            f"  Credentials captured in plaintext — no decryption needed."
        )


    return demo


def _calc_confidence(scenario: dict, pii_map: dict, findings: list[dict] | None = None) -> str:
    """
    Calculate how feasible the attack is based on available PII.
    Optionally weights by AI confidence of underlying findings.
    """
    present = sum(1 for f in scenario["requires"] + scenario["optional"] if f in pii_map)
    total   = len(scenario["requires"]) + len(scenario["optional"]) or 1
    pct     = present / total
    if pct >= 0.8: return "Very High"
    if pct >= 0.5: return "High"
    if pct >= 0.3: return "Medium"
    return "Low"


# ── Dynamic Scenario Builder ──────────────────────────────────────────────────

def _build_dynamic_scenarios(pii_map: dict, already_fired: set) -> list[dict]:
    """
    Generate contextual attack scenarios for PII combinations NOT covered
    by the static SCENARIOS list. Avoids duplicating already-fired scenarios.
    """
    dynamic = []

    # ── 1. email + location → Location-Targeted Phishing ─────────────────────
    if "email" in pii_map and "location" in pii_map and "phishing_email" not in already_fired:
        email    = pii_map["email"][0]
        location = pii_map["location"][0]
        dynamic.append({
            "id":          "location_phishing",
            "name":        "Location-Targeted Phishing",
            "icon":        "map-pin",
            "severity":    "HIGH",
            "color":       "#ef4444",
            "description": "Your email combined with your location enables geographically-targeted phishing attacks posing as local banks, government offices, or utilities.",
            "steps": [
                f"Attacker knows your email ({email}) and location ({location}).",
                "Crafts a phishing email posing as your local bank, electricity board, or municipality.",
                "Message references local events or services to appear legitimate.",
                "You trust the local reference and click the malicious link.",
                "Credentials are stolen or malware is installed.",
            ],
            "mitigations": [
                "Never share your location publicly alongside your email.",
                "Verify any local service emails by calling the organisation directly.",
                "Use separate email addresses for public and private use.",
            ],
            "demo": {
                "email_preview": (
                    f"From: alerts@{location.lower().replace(' ', '-').replace(',', '')}-citybank.com\n"
                    f"To: {email}\n"
                    f"Subject: Urgent: Your account in {location} requires verification\n\n"
                    f"Dear Customer,\n\nWe detected a suspicious login to your account\n"
                    f"from a device outside {location}.\n\n"
                    f"Click here to verify: http://secure-{location.lower().replace(' ','')}-verify.malicious.xyz"
                )
            },
            "confidence": "High",
        })

    # ── 2. credit_card alone (no CVV) → Card Cloning / Skimming ──────────────
    if "credit_card" in pii_map and "card_cloning" not in already_fired:
        card = pii_map["credit_card"][0]
        dynamic.append({
            "id":          "card_cloning",
            "name":        "Card Cloning / Skimming",
            "icon":        "credit-card",
            "severity":    "CRITICAL",
            "color":       "#dc2626",
            "description": "Your card number, even without CVV, can be used for card-not-present online fraud or sold to criminal networks for skimming attacks.",
            "steps": [
                f"Attacker has your card number: {card[:4]}****.",
                "Sells the number on dark-web carding forums for $5–$20.",
                "Buyers attempt card-not-present purchases on sites without CVV checks.",
                "Some merchants (especially international) process without CVV → fraud succeeds.",
                "Your card is charged; dispute process takes weeks.",
            ],
            "mitigations": [
                "Report the card number to your bank and request a replacement immediately.",
                "Set up transaction alerts so you see every charge in real-time.",
                "Enable virtual card numbers for online purchases (most banks offer this).",
                "Review your statement for unauthorised charges.",
            ],
            "demo": {
                "attack_preview": (
                    f"Card number acquired: {card[:4]} **** **** ****\n\n"
                    f"Dark-web listing: '$8.99 — card number, works for CNP purchases'\n\n"
                    f"Test purchases attempted:\n"
                    f"  aliexpress.com   → SUCCESS (no CVV required)\n"
                    f"  digital downloads → SUCCESS (instant delivery, no shipping check)\n\n"
                    f"Your bank notified you 3 days later."
                )
            },
            "confidence": "Very High",
        })

    # ── 3. aadhaar + pan_card → Full KYC Identity Theft ──────────────────────
    if "aadhaar" in pii_map and "pan_card" in pii_map and "full_kyc_theft" not in already_fired:
        aadhaar = pii_map["aadhaar"][0]
        pan     = pii_map["pan_card"][0]
        dynamic.append({
            "id":          "full_kyc_theft",
            "name":        "Full KYC Identity Theft (Aadhaar + PAN)",
            "icon":        "shield",
            "severity":    "CRITICAL",
            "color":       "#7f1d1d",
            "description": "Having both Aadhaar and PAN is a complete KYC (Know Your Customer) package. An attacker can open bank accounts, obtain loans, and register businesses in your name.",
            "steps": [
                f"Attacker has your Aadhaar ({aadhaar[:4]}****) AND PAN ({pan[:3]}*******).",
                "Opens a full-KYC bank account at an online bank → approved instantly via e-KYC.",
                "Registers a shell company under your name and PAN.",
                "Takes out personal loans of ₹5–25 lakhs — your CIBIL score collapses.",
                "Income Tax notices arrive at your address. Legal resolution takes 1–3 years.",
            ],
            "mitigations": [
                "Lock your Aadhaar biometrics at myaadhaar.uidai.gov.in immediately.",
                "File a complaint at cybercrime.gov.in with both document numbers.",
                "Check CIBIL report weekly for new accounts or enquiries.",
                "Alert Income Tax Dept and request a freeze on PAN-linked filings.",
            ],
            "demo": {
                "fraud_preview": (
                    f"Full KYC package:\n"
                    f"  Aadhaar: {aadhaar[:4]} **** ****\n"
                    f"  PAN:     {pan[:3]}*******\n\n"
                    f"Attacker actions within 72 hours:\n"
                    f"  1. Opens digital bank account (e-KYC auto-approved)\n"
                    f"  2. Gets ₹50,000 instant loan from a NBFC\n"
                    f"  3. Registers a GST-registered firm under your PAN\n"
                    f"  4. Your credit score drops 200+ points\n"
                    f"  5. IT Department issues tax notice to your address"
                )
            },
            "confidence": "Very High",
        })

    # ── 4. person_name + organization + location → Impersonation ─────────────
    if ("person_name" in pii_map and "organization" in pii_map
            and "location" in pii_map and "impersonation" not in already_fired
            and "spear_phishing" not in already_fired):
        name = pii_map["person_name"][0]
        org  = pii_map["organization"][0]
        loc  = pii_map["location"][0]
        dynamic.append({
            "id":          "impersonation",
            "name":        "Real-World Impersonation",
            "icon":        "user",
            "severity":    "HIGH",
            "color":       "#b45309",
            "description": "Your name, employer, and location enable an attacker to impersonate you to colleagues, HR departments, or government offices.",
            "steps": [
                f"Attacker knows: {name} | {org} | {loc}.",
                "Contacts your HR department claiming to update bank account for salary.",
                "Sends official-looking emails to colleagues requesting urgent wire transfers.",
                "Visits local government office using your identity for document fraud.",
                "By the time the fraud is discovered, damage to reputation and finances is done.",
            ],
            "mitigations": [
                "Remove your employer and location from public profiles and documents.",
                "Inform your HR to verify any account-change requests via a secondary channel.",
                "Set up a personal verification codeword with close colleagues.",
            ],
            "demo": {
                "email_preview": (
                    f"From: {name.lower().replace(' ', '.')}@{org.lower().replace(' ', '')}-hr.com\n"
                    f"To: payroll@{org.lower().replace(' ', '')}.com\n"
                    f"Subject: Salary account update request\n\n"
                    f"Hi,\n\nThis is {name} from {org}, {loc} office.\n"
                    f"Please update my salary account details effective this month.\n\n"
                    f"New account: [attacker's account details]"
                )
            },
            "confidence": "High",
        })

    # ── 5. dob + person_name → Birthday Social Engineering ───────────────────
    if "dob" in pii_map and "person_name" in pii_map and "birthday_social_eng" not in already_fired:
        name = pii_map["person_name"][0]
        dob  = pii_map["dob"][0]
        dynamic.append({
            "id":          "birthday_social_eng",
            "name":        "Birthday-Based Social Engineering",
            "icon":        "calendar",
            "severity":    "MEDIUM",
            "color":       "#d97706",
            "description": "Your name and date of birth are used as security questions and identity verification by banks, telecoms, and government services. An attacker can impersonate you by quoting them.",
            "steps": [
                f"Attacker knows: {name}, DOB: {dob}.",
                "Calls your bank or telecom pretending to be you.",
                "Passes 'Name + DOB' identity verification (used by most Indian banks and telecoms).",
                "Requests a duplicate SIM, changes account email, or resets mobile banking PIN.",
                "You lose access to your accounts before you realise the breach.",
            ],
            "mitigations": [
                "Remove your date of birth from all public documents and social profiles.",
                "Set up an additional security PIN with your bank beyond Name+DOB.",
                "Use phone-number-based 2FA, not knowledge-based answers alone.",
            ],
            "demo": {
                "call_script": (
                    f"Attacker → Bank: 'I'd like to update my registered email.'\n"
                    f"Bank: 'Please confirm your full name and date of birth.'\n"
                    f"Attacker: 'My name is {name}, DOB is {dob}.'\n"
                    f"Bank: 'Verified. What email would you like to update to?'\n"
                    f"Attacker: 'attacker@evil.com'\n"
                    f"Bank: 'Done. You will receive OTPs on the new email from now.'"
                )
            },
            "confidence": "Medium",
        })

    # ── 6. phone + email + person_name (all 3) → Identity Aggregation Scam ──
    if ("phone" in pii_map and "email" in pii_map and "person_name" in pii_map
            and "account_takeover" not in already_fired
            and "identity_aggregation" not in already_fired):
        name  = pii_map["person_name"][0]
        email = pii_map["email"][0]
        phone = pii_map["phone"][0]
        dynamic.append({
            "id":          "identity_aggregation",
            "name":        "Identity Aggregation + Targeted Scam",
            "icon":        "database",
            "severity":    "HIGH",
            "color":       "#ef4444",
            "description": "With your name, email, and phone number together, attackers build a complete contact profile and target you with highly personalised scam calls, WhatsApp messages, and emails simultaneously.",
            "steps": [
                f"Attacker aggregates: {name} | {email} | {phone}.",
                "Sells the complete profile to scam call centres for $0.50–$2 per record.",
                "You receive a call from 'your bank' using your name — sounds completely real.",
                "While on call, a phishing email arrives at your inbox, and a WhatsApp follows.",
                "Triple-channel pressure causes many victims to share OTPs or transfer money.",
            ],
            "mitigations": [
                "Never confirm personal details to inbound callers — always call back on official numbers.",
                "Register on the DND registry (1909) to reduce unsolicited calls.",
                "Use different email addresses for banking vs public registrations.",
                "Enable 'Truecaller' spam detection or equivalent.",
            ],
            "demo": {
                "attack_preview": (
                    f"Profile sold to scam centre:\n"
                    f"  Name:  {name}\n"
                    f"  Email: {email}\n"
                    f"  Phone: {phone}\n\n"
                    f"Attack sequence (same day):\n"
                    f"  09:15 — Call from '+91-XXXX' (spoofed bank number): '{name}, your account is blocked.'\n"
                    f"  09:16 — Phishing email arrives at {email}: 'Account suspension notice'\n"
                    f"  09:17 — WhatsApp from unknown: 'Share OTP to restore access'\n"
                    f"  09:18 — Victim under pressure → shares OTP → account drained."
                )
            },
            "confidence": "High",
        })

    return dynamic
