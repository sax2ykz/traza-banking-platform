"""Run locally on an isolated dev machine after migration 003. Password never echoed."""
import argparse
import getpass
import sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import hash_password
from app.security_models import AppUser
from app.session import SessionLocal


def main():
    parser = argparse.ArgumentParser(description='Bootstrap a single TRAZA administrator')
    parser.add_argument('--email', default='operaciones@trazabancocloud.com')
    args = parser.parse_args()
    email = args.email.lower().strip()
    with SessionLocal() as db:
        if db.scalar(select(AppUser.id).where(AppUser.email == email)):
            print('Admin already exists. No changes made.')
            return
        password = getpass.getpass('Dev admin password (not displayed): ')
        confirmation = getpass.getpass('Confirm dev admin password: ')
        if password != confirmation:
            sys.exit('Password confirmation does not match')
        try:
            hashed = hash_password(password)
        except ValueError as exc:
            sys.exit(str(exc))
        db.add(AppUser(id=uuid4(), email=email, password_hash=hashed, role='ADMIN', customer_id=None))
        db.commit()
    print('TRAZA administrator created successfully.')


if __name__ == '__main__':
    main()
