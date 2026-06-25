def calculate_privacy_score(emails, phones, passwords, unsafe_image=False):
    score = 0

    # 🔷 TEXT BASED SCORING
    score += len(emails) * 10
    score += len(phones) * 8
    score += len(passwords) * 15

    # 🔥 IMAGE RISK (NEW)
    if unsafe_image:
        score += 25   # strong impact

    # 🔷 RISK LEVEL
    if score >= 50:
        risk = "HIGH"
    elif score >= 20:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return score, risk, {
        "emails": len(emails),
        "phones": len(phones),
        "passwords": len(passwords),
        "image_risk": unsafe_image
    }