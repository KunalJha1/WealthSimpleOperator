"""
Migration script to update account tiers based on portfolio AUM.

Does NOT delete any data - only updates the account_tier field for existing clients.

Core: $1 - $100k
Premium: $100k - $500k
Generation: $500k+
"""

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from db import SessionLocal
from models import Client, Portfolio


def get_account_tier_for_aum(aum: float) -> str:
    """Assign account tier based on total portfolio value."""
    if aum < 100_000:
        return "Core"
    elif aum < 500_000:
        return "Premium"
    else:
        return "Generation"


def migrate_account_tiers() -> None:
    """Update account_tier for all clients based on their total portfolio AUM."""
    session = SessionLocal()
    try:
        # Get all clients with their portfolios
        clients = session.query(Client).options(
            joinedload(Client.portfolios)
        ).all()

        updated_count = 0
        for client in clients:
            if not client.portfolios:
                # No portfolios, assign Core tier
                client.account_tier = "Core"
                updated_count += 1
                continue

            # Sum all portfolio values for this client
            total_aum = sum(float(p.total_value) for p in client.portfolios)

            # Assign tier based on AUM
            new_tier = get_account_tier_for_aum(total_aum)

            if client.account_tier != new_tier:
                print(f"  {client.name:30s} | AUM: ${total_aum:>12,.0f} | {client.account_tier or 'None':12s} → {new_tier}")
                client.account_tier = new_tier
                updated_count += 1
            else:
                print(f"  {client.name:30s} | AUM: ${total_aum:>12,.0f} | {new_tier} (no change)")

        session.commit()
        print(f"\nMigration complete! Updated {updated_count} clients.")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("Migrating account tiers based on portfolio AUM...\n")
    migrate_account_tiers()
