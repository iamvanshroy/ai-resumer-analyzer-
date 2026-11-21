"""
auth.py
-------
Small local login system for the recruiter (the person who hires).

* Accounts are saved in recruiters.json next to the program (this computer only).
* Passwords are NEVER saved as text. Each password is salted and hashed with PBKDF2-HMAC-SHA256.
* This protects the app on one computer; it is not an online authentication server.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

USERS_FILE = Path(__file__).resolve().parent / "recruiters.json"
ITERATIONS = 200_000
MIN_PASSWORD = 6
DEMO_EMAIL, DEMO_PASSWORD, DEMO_NAME, DEMO_COMPANY = "demo@recruiter.com", "Demo@123", "Demo Recruiter", "Demo Company"


class AuthError(Exception):
    """A message that is safe to show to the user."""


def _load() -> dict:
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(users: dict) -> None:
    tmp = USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(users, indent=2), encoding="utf-8")
    os.replace(tmp, USERS_FILE)


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS).hex()


def valid_email(email: str) -> bool:
    return re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", email) is not None


def register(name: str, company: str, email: str, password: str) -> dict:
    name, company, email = name.strip(), company.strip(), email.strip().lower()
    if len(name) < 2:
        raise AuthError("Please enter your full name.")
    if not company:
        raise AuthError("Please enter your company name.")
    if not valid_email(email):
        raise AuthError("Please enter a valid email address.")
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Password must have at least {MIN_PASSWORD} characters.")
    users = _load()
    if email in users:
        raise AuthError("An account with this email already exists. Please sign in.")
    salt = secrets.token_bytes(16)
    users[email] = {"name": name, "company": company, "salt": salt.hex(),
                    "hash": _hash(password, salt), "created": time.strftime("%Y-%m-%d %H:%M")}
    _save(users)
    return {"name": name, "company": company, "email": email}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    if not email or not password:
        raise AuthError("Enter your email and password.")
    rec = _load().get(email)
    salt = bytes.fromhex(rec["salt"]) if rec else b"\x00" * 16
    ok = hmac.compare_digest(_hash(password, salt), rec["hash"] if rec else "0" * 64)
    if not rec or not ok:
        raise AuthError("Incorrect email or password.")        # same message for both, on purpose
    return {"name": rec["name"], "company": rec["company"], "email": email}


def ensure_demo() -> dict:
    """Create the demo recruiter account if it does not exist yet, then sign in with it."""
    if DEMO_EMAIL not in _load():
        register(DEMO_NAME, DEMO_COMPANY, DEMO_EMAIL, DEMO_PASSWORD)
    return login(DEMO_EMAIL, DEMO_PASSWORD)
