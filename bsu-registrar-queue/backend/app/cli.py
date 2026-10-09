"""
Server-side account recovery - the "break glass" path for when no admin can
log in to reset a password through the app.

    cd backend
    python -m app.cli reset-password <username>              # you pick it, use it as-is
    python -m app.cli reset-password <username> --temporary  # forced change at next login
    python -m app.cli gmail-auth                             # one-time email setup (app/gmail_auth.py)

Prompts for the new password without echoing it, and clears any failed-login
lock. Whoever can run this already holds DATABASE_URL, so it grants nothing
they couldn't do with direct database access - it just does it safely
(bcrypt hash, audit line) instead of by hand-written SQL.
"""
import argparse
import getpass
import sys
from typing import Callable, Optional

from sqlalchemy.orm import Session

from .core.audit import log_security_event
from .core.security import reset_user_password
from .db_models import UserDB

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # bcrypt's limit, same cap as the API models


def _reset_password(db: Session, username: str, temporary: bool, prompt: Callable[[str], str]) -> int:
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user is None:
        print(f"No account named '{username}'.", file=sys.stderr)
        return 1

    password = prompt(f"New password for '{username}': ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        print(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.", file=sys.stderr)
        return 1
    if prompt("Confirm new password: ") != password:
        print("Passwords do not match - nothing changed.", file=sys.stderr)
        return 1

    reset_user_password(user, password, must_change=temporary)
    db.commit()
    log_security_event(
        "auth.password_reset", outcome="success",
        actor="server-cli", target=user.username,
        detail="temporary password set" if temporary else "password set",
    )

    print(f"Password for '{username}' updated and account unlocked.")
    if temporary:
        print("They will be asked to choose a new password at their next login.")
    if not user.is_active:
        print(
            f"Note: '{username}' is deactivated - an admin must reactivate it "
            "before it can log in."
        )
    return 0


def run(argv: list[str], db: Session, prompt: Callable[[str], str] = getpass.getpass) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="BSU Registrar Queue account recovery")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("gmail-auth", help="get the Gmail API refresh token for sending email (see app/gmail_auth.py)")
    reset = sub.add_parser("reset-password", help="set a staff account's password and unlock it")
    reset.add_argument("username")
    reset.add_argument(
        "--temporary", action="store_true",
        help="make the user choose a new password at their next login",
    )
    args = parser.parse_args(argv)

    if args.command == "reset-password":
        return _reset_password(db, args.username, args.temporary, prompt)
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Email setup needs no database - don't connect (or print one) for it.
    if argv[:1] == ["gmail-auth"]:
        from . import gmail_auth
        return gmail_auth.run(argv[1:])

    from .core.database import SessionLocal, engine

    # DATABASE_URL may well be production - say which database this touches.
    print(f"Database: {engine.url.host or 'localhost'}/{engine.url.database}")
    db = SessionLocal()
    try:
        return run(argv, db)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
