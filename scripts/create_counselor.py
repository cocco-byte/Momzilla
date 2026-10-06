#!/usr/bin/env python3
"""Provision a counselor account.

Run this once per counselor rather than seeding accounts in source code -
passwords should never live in a file that ends up in version control.

    python scripts/create_counselor.py
"""

import getpass
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import db
from backend.auth import hash_password


def main() -> None:
    db.init_db()

    name = input("Counselor name: ").strip()
    email = input("Contact email: ").strip()
    username = input("Login username: ").strip()

    if db.get_counselor_by_username(username) is not None:
        print(f"A counselor with username '{username}' already exists.")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match.")
        sys.exit(1)
    if len(password) < 12:
        print("Use at least 12 characters - this account can see real student alerts.")
        sys.exit(1)

    db.create_counselor(
        id=str(uuid.uuid4()),
        name=name,
        contact_email=email,
        username=username,
        password_hash=hash_password(password),
    )
    print(f"Created counselor account '{username}'.")


if __name__ == "__main__":
    main()
