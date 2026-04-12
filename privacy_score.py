def calculate_privacy_score(emails, phones, passwords, unsafe_image=False):
    score = 0
    reasons = []

    if len(emails) > 0:
        score = score + 20 * len(emails)
        reasons.append("Email ID detected")

    if len(phones) > 0:
        score = score + 30 * len(phones)
        reasons.append("Phone number detected")

    if len(passwords) > 0:
        score = score + 40 * len(passwords)
        reasons.append("Password-like text detected")

    if unsafe_image:
        score = score + 50
        reasons.append("Potentially unsafe image")

    if score <= 30:
        risk = "LOW"
    elif score <= 70:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    return score, risk, reasons
