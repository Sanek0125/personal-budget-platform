from decimal import ROUND_HALF_UP, Decimal

from app.models.reward import CashbackRule, RewardProgram
from app.models.transaction import Transaction
from app.schemas.reward import ExpectedRewardRead

MONEY_QUANT = Decimal("0.000001")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _transaction_category_ids(transaction: Transaction) -> set[object]:
    category_ids: set[object] = set()
    if transaction.category_id is not None:
        category_ids.add(transaction.category_id)
    for split in getattr(transaction, "splits", []) or []:
        if split.category_id is not None:
            category_ids.add(split.category_id)
    return category_ids


def _merchant_text(transaction: Transaction) -> str:
    return " ".join(
        value or ""
        for value in (
            transaction.merchant_name,
            transaction.merchant_raw,
            transaction.description,
        )
    ).lower()


def rule_matches_transaction(rule: CashbackRule, transaction: Transaction) -> bool:
    if not rule.is_active:
        return False
    if rule.spend_currency_code != transaction.currency_code:
        return False
    spend_amount = abs(transaction.amount)
    if rule.min_spend_amount is not None and spend_amount < rule.min_spend_amount:
        return False
    if (
        rule.category_id is not None
        and rule.category_id not in _transaction_category_ids(transaction)
    ):
        return False
    if rule.merchant_pattern:
        if rule.merchant_pattern.lower() not in _merchant_text(transaction):
            return False
    return True


def find_matching_cashback_rule(
    rules: list[CashbackRule], transaction: Transaction
) -> CashbackRule | None:
    matching = [rule for rule in rules if rule_matches_transaction(rule, transaction)]
    if not matching:
        return None
    return sorted(matching, key=lambda rule: (rule.priority, rule.created_at or ""))[0]


def calculate_reward_for_transaction(
    program: RewardProgram, transaction: Transaction, rules: list[CashbackRule]
) -> ExpectedRewardRead | None:
    if transaction.status != "posted" or transaction.deleted_at is not None:
        return None
    if transaction.type != "expense" or transaction.amount >= 0:
        return None

    rule = find_matching_cashback_rule(rules, transaction)
    if rule is None:
        return None

    amount = _quantize(abs(transaction.amount) * rule.rate)
    if rule.max_reward_amount is not None:
        amount = min(amount, _quantize(rule.max_reward_amount))

    return ExpectedRewardRead(
        program_id=program.id,
        rule_id=rule.id,
        source_transaction_id=transaction.id,
        reward_kind=program.program_type,
        amount=amount,
        currency_code=program.currency_code,
        description=f"Expected {program.name} reward for {transaction.description}",
    )
