import argparse
import asyncio
import getpass

from pydantic import ValidationError
from sqlalchemy import select

from homelab_pulse.database import async_session_factory
from homelab_pulse.models.user import User, UserRole
from homelab_pulse.schemas.user import UserCreate
from homelab_pulse.security import hash_password


async def create_admin(name: str, email: str) -> None:
    normalized_email = email.lower()

    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == normalized_email))
        if user is not None:
            user.role = UserRole.ADMIN
            await session.commit()
            print(f"Administrator permission granted to {normalized_email}.")
            return

        password = getpass.getpass("Password: ")
        password_confirmation = getpass.getpass("Confirm password: ")
        if password != password_confirmation:
            raise SystemExit("Passwords do not match.")

        try:
            payload = UserCreate(name=name, email=normalized_email, password=password)
        except ValidationError as error:
            raise SystemExit(str(error)) from error

        session.add(
            User(
                name=payload.name.strip(),
                email=str(payload.email).lower(),
                password_hash=hash_password(payload.password),
                role=UserRole.ADMIN,
            )
        )
        await session.commit()
        print(f"Administrator {normalized_email} created.")


def main() -> None:
    parser = argparse.ArgumentParser(description="HomeLab Pulse administration commands")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subcommands.add_parser("create-admin")
    create_admin_parser.add_argument("--name", required=True)
    create_admin_parser.add_argument("--email", required=True)

    arguments = parser.parse_args()
    if arguments.command == "create-admin":
        asyncio.run(create_admin(arguments.name, arguments.email))


if __name__ == "__main__":
    main()
