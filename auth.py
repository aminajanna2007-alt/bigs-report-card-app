import hashlib
import binascii
import os
import re

# ---------- Password Hashing ----------
def make_pbkdf2_hash(password, iterations=200000):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_password(stored, provided):
    try:
        if isinstance(stored, str) and stored.startswith("pbkdf2$"):
            _, iters, salt_hex, stored_hash = stored.split('$')
            salt = binascii.unhexlify(salt_hex)
            dk = hashlib.pbkdf2_hmac('sha256', provided.encode(), salt, int(iters))
            return binascii.hexlify(dk).decode() == stored_hash
        return stored == provided
    except Exception:
        return False

# ---------- Username / Password Generation Logic ----------
def generate_username(first_name, last_name):
    """
    1. Take the first name
    2. Take the first 3 letters of the last name
    3. Convert everything to lowercase
    4. Join them without spaces
    """
    if not first_name: return ""
    fname = first_name.strip().lower()
    lname = last_name.strip().lower() if last_name else ""
    lname_part = lname[:3]
    return f"{fname}{lname_part}"

def generate_password(first_name, last_name):
    """
    1. Take first 2 letters of first name
    2. Take last 2 letters of last name
    3. Add a fixed number 26
    4. Add one special character (!)
    """
    if not first_name: return ""
    fname = first_name.strip()
    lname = last_name.strip() if last_name else ""
    
    p1 = fname[:2]
    p2 = lname[-2:] if len(lname) >= 2 else lname
    
    # If names are too short, we handle gracefully, but logic implies valid names.
    return f"{p1}{p2}26!"
