from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.models.budget import Budget, BudgetLimit
from app.models.transaction import Transaction
from app.schemas.budget import BudgetLimitProgress, BudgetProgressRead

_MONEY_QUANT = Decimal("0.000001")
_PERCENT_QUANT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def _percent(spent: Decimal, limit: Decimal) -> Decimal:
    if limit == 0:
        return Decimal("0.00")
    return ((spent / limit) * Decimal("100")).quantize(
        _PERCENT_QUANT, rounding=ROUND_HALF_UP
    )


def _transaction_amount_in_budget_currency(
    transaction: Transaction, budget_currency_code: str
) -> Decimal | None:
    if transaction.currency_code == budget_currency_code:
        return transaction.amount
    if (
        transaction.base_currency_code == budget_currency_code
        and transaction.base_amount is not None
    ):
        return transaction.base_amount
    return None


def _split_amount_in_budget_currency(
    transaction: Transaction, split_amount: Decimal, budget_currency_code: str
) -> Decimal | None:
    if transaction.currency_code == budget_currency_code:
        return split_amount
    amount = _transaction_amount_in_budget_currency(transaction, budget_currency_code)
    if amount is None or transaction.amount == 0:
        return None
    return amount * (split_amount / transaction.amount)


def _expense_value(amount: Decimal) -> Decimal:
    if amount >= 0:
        return Decimal("0")
    return -amount


def calculate_budget_progress(
    budget: Budget,
    limits: list[BudgetLimit],
    transactions: list[Transaction],
) -> BudgetProgressRead:
    """Calculate category budget progress for posted non-deleted expenses.

    Split transactions count by split category. Non-split transactions count by
    transaction category. Amounts are converted only when the transaction carries
    a base amount in the budget currency; otherwise unmatched currencies are ignored.
    """

    spent_by_category: dict[UUID, Decimal] = {
        limit.category_id: Decimal("0") for limit in limits
    }

    for transaction in transactions:
        if transaction.deleted_at is not None or transaction.status != "posted":
            continue
        if transaction.type != "expense":
            continue
        if transaction.workspace_id != budget.workspace_id:
            continue
        if transaction.occurred_at.date() < budget.period_start:
            continue
        if transaction.occurred_at.date() > budget.period_end:
            continue

        splits = list(getattr(transaction, "splits", []) or [])
        if splits:
            for split in splits:
                if split.category_id not in spent_by_category:
                    continue
                amount = _split_amount_in_budget_currency(
                    transaction, split.amount, budget.currency_code
                )
                if amount is not None:
                    spent_by_category[split.category_id] += _expense_value(amount)
            continue

        category_id = transaction.category_id
        if category_id not in spent_by_category:
            continue
        amount = _transaction_amount_in_budget_currency(
            transaction, budget.currency_code
        )
        if amount is not None and category_id is not None:
            spent_by_category[category_id] += _expense_value(amount)

    limit_progress: list[BudgetLimitProgress] = []
    for limit in limits:
        spent = _money(spent_by_category.get(limit.category_id, Decimal("0")))
        amount = _money(limit.amount)
        limit_progress.append(
            BudgetLimitProgress(
                category_id=limit.category_id,
                limit_amount=amount,
                spent_amount=spent,
                remaining_amount=_money(amount - spent),
                percent_used=_percent(spent, amount),
                currency_code=budget.currency_code,
            )
        )

    total_limit = _money(sum((limit.amount for limit in limits), Decimal("0")))
    total_spent = _money(
        sum((item.spent_amount for item in limit_progress), Decimal("0"))
    )
    return BudgetProgressRead(
        budget_id=budget.id,
        period_start=budget.period_start,
        period_end=budget.period_end,
        currency_code=budget.currency_code,
        total_limit=total_limit,
        total_spent=total_spent,
        total_remaining=_money(total_limit - total_spent),
        limits=limit_progress,
    )
