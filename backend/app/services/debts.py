from collections import defaultdict
from decimal import Decimal

from app.models.debt import Debt
from app.schemas.debt import DebtSummaryRead, DebtSummaryTotal


def paid_amount(debt: Debt) -> Decimal:
    return sum((payment.amount for payment in debt.payments), Decimal("0"))


def remaining_amount(debt: Debt) -> Decimal:
    if debt.status == "cancelled":
        return Decimal("0")
    remaining = debt.principal_amount - paid_amount(debt)
    return max(remaining, Decimal("0"))


def calculate_debt_summary(debts: list[Debt]) -> DebtSummaryRead:
    totals: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: {
            "principal_amount": Decimal("0"),
            "paid_amount": Decimal("0"),
            "remaining_amount": Decimal("0"),
        }
    )
    for debt in debts:
        if debt.status in {"paid", "cancelled"}:
            continue
        key = (debt.direction, debt.currency_code)
        paid = paid_amount(debt)
        totals[key]["principal_amount"] += debt.principal_amount
        totals[key]["paid_amount"] += paid
        totals[key]["remaining_amount"] += debt.principal_amount - paid

    return DebtSummaryRead(
        totals=[
            DebtSummaryTotal(
                direction=direction,  # type: ignore[arg-type]
                currency_code=currency_code,
                principal_amount=amounts["principal_amount"],
                paid_amount=amounts["paid_amount"],
                remaining_amount=amounts["remaining_amount"],
            )
            for (direction, currency_code), amounts in sorted(
                totals.items(),
                key=lambda item: (item[0][0] != "they_owe_me", item[0][1]),
            )
        ]
    )
