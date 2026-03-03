"""
Generate realistic portfolio holdings for all existing clients based on their risk profiles.
This populates the positions table with ETFs matched to risk profile.
"""
from db import session_scope
from models import Client, Portfolio, Position

# Risk profile to asset allocation mapping
RISK_PROFILES = {
    "Conservative": {
        "Fixed Income": 0.70,
        "Equity": 0.20,
        "Cash": 0.10,
        "etfs": ["SGOV", "XGB", "VSB", "XCB", "GIC"],  # Bond-heavy
    },
    "Moderate Conservative": {
        "Fixed Income": 0.55,
        "Equity": 0.35,
        "Cash": 0.10,
        "etfs": ["XGB", "VSB", "XUU", "VUN", "XIC"],
    },
    "Balanced": {
        "Fixed Income": 0.40,
        "Equity": 0.50,
        "Cash": 0.10,
        "etfs": ["VFV", "XUU", "XIC", "VSB", "XGB"],
    },
    "Moderate Growth": {
        "Fixed Income": 0.25,
        "Equity": 0.65,
        "Cash": 0.10,
        "etfs": ["VFV", "XUU", "XIC", "VUN", "VSB"],
    },
    "Growth": {
        "Fixed Income": 0.10,
        "Equity": 0.80,
        "Cash": 0.10,
        "etfs": ["VFV", "XUU", "XIC", "VUN", "XIT"],  # Equity/tech heavy
    },
    "Aggressive Growth": {
        "Fixed Income": 0.05,
        "Equity": 0.85,
        "Cash": 0.10,
        "etfs": ["XIT", "VFV", "XUU", "VUN", "XIC"],  # Heavy tech exposure
    },
}

# Asset class for each ETF
ETF_ASSET_CLASS = {
    "SGOV": "Fixed Income",
    "XGB": "Fixed Income",
    "VSB": "Fixed Income",
    "XCB": "Fixed Income",
    "GIC": "Fixed Income",
    "VFV": "Equity",
    "XUU": "Equity",
    "XIC": "Equity",
    "VUN": "Equity",
    "XIT": "Equity",
}

def generate_holdings():
    """Generate holdings for all clients based on risk profile."""
    with session_scope() as db:
        clients = db.query(Client).all()

        for client in clients:
            print(f"\nGenerating holdings for {client.name} ({client.risk_profile})...")

            # Get risk profile allocation
            profile = client.risk_profile or "Balanced"
            allocation = RISK_PROFILES.get(profile, RISK_PROFILES["Balanced"])
            etfs = allocation["etfs"]

            # Get or create portfolio
            portfolio = db.query(Portfolio).filter(
                Portfolio.client_id == client.id
            ).first()

            if not portfolio:
                portfolio = Portfolio(
                    client_id=client.id,
                    name=f"{client.name}'s Portfolio",
                    total_value=float(client.aum or 250000),
                    target_equity_pct=allocation["Equity"],
                    target_fixed_income_pct=allocation["Fixed Income"],
                    target_cash_pct=allocation["Cash"],
                )
                db.add(portfolio)
                db.flush()
                print(f"  [+] Created portfolio for {client.name}")

            # Clear existing positions
            existing_positions = db.query(Position).filter(
                Position.portfolio_id == portfolio.id
            ).all()
            for pos in existing_positions:
                db.delete(pos)
            db.flush()

            # Generate positions based on allocation
            portfolio_value = float(portfolio.total_value)
            equity_value = portfolio_value * allocation["Equity"]
            fixed_income_value = portfolio_value * allocation["Fixed Income"]
            cash_value = portfolio_value * allocation["Cash"]

            # Distribute equity ETFs
            equity_etfs = [e for e in etfs if ETF_ASSET_CLASS.get(e) == "Equity"]
            if equity_etfs:
                per_etf_value = equity_value / len(equity_etfs)
                for etf in equity_etfs:
                    pos = Position(
                        portfolio_id=portfolio.id,
                        ticker=etf,
                        asset_class="Equity",
                        weight=allocation["Equity"] / len(equity_etfs),
                        value=per_etf_value,
                    )
                    db.add(pos)

            # Distribute fixed income ETFs
            fi_etfs = [e for e in etfs if ETF_ASSET_CLASS.get(e) == "Fixed Income"]
            if fi_etfs:
                per_etf_value = fixed_income_value / len(fi_etfs)
                for etf in fi_etfs:
                    pos = Position(
                        portfolio_id=portfolio.id,
                        ticker=etf,
                        asset_class="Fixed Income",
                        weight=allocation["Fixed Income"] / len(fi_etfs),
                        value=per_etf_value,
                    )
                    db.add(pos)

            # Cash position
            if cash_value > 0:
                pos = Position(
                    portfolio_id=portfolio.id,
                    ticker="CASH",
                    asset_class="Cash",
                    weight=allocation["Cash"],
                    value=cash_value,
                )
                db.add(pos)

            db.flush()
            position_count = db.query(Position).filter(
                Position.portfolio_id == portfolio.id
            ).count()
            print(f"  [+] Added {position_count} positions")
            print(f"    - Equity: {allocation['Equity']*100:.0f}% (${equity_value:,.0f})")
            print(f"    - Fixed Income: {allocation['Fixed Income']*100:.0f}% (${fixed_income_value:,.0f})")
            print(f"    - Cash: {allocation['Cash']*100:.0f}% (${cash_value:,.0f})")

        print(f"\n[OK] Generated holdings for {len(clients)} clients")

if __name__ == "__main__":
    generate_holdings()
