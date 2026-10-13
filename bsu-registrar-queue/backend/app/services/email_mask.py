"""
Masked email addresses for public responses - enough for a student to
recognise their own address (and spot a typo in the domain), not enough to
harvest addresses by guessing student numbers.
"""


def mask_email(email: str) -> str:
    """juan.delacruz@gmail.com -> j***@gmail.com; x@yahoo.com -> *@yahoo.com"""
    local, sep, domain = (email or "").partition("@")
    if not sep:
        return "***"
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"
