"""Helpers for internal placeholder emails used by optional student email flows."""

from typing import Optional


TEMP_EMAIL_DOMAIN = "@temp.com"


def build_placeholder_email(account: str) -> str:
    return f"{account}{TEMP_EMAIL_DOMAIN}"


def is_placeholder_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.endswith(TEMP_EMAIL_DOMAIN)


def to_public_email(email: Optional[str]) -> str:
    if is_placeholder_email(email):
        return ""
    return email or ""
