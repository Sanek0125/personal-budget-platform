"""Category rule matching: operators, priority order, and rule selection."""

import re
from decimal import Decimal

from app.models.category_rule import CategoryRule
from app.models.transaction import Transaction

# Operators that compare a text field against ``pattern``. ``amount_between``
# is handled separately because it compares the numeric transaction amount.
TEXT_OPERATORS: frozenset[str] = frozenset(
    {"contains", "equals", "starts_with", "regex"}
)
MATCH_FIELDS: frozenset[str] = frozenset(
    {"description", "merchant_name", "merchant_raw"}
)

# Tie-breaker when two rules share the same explicit ``priority``: more
# specific operators are evaluated first. Lower number wins.
OPERATOR_PRIORITY: dict[str, int] = {
    "equals": 0,
    "starts_with": 1,
    "regex": 2,
    "contains": 3,
    "amount_between": 4,
}

# ReDoS mitigation. User-supplied regex patterns are bounded in length, and
# the value they are matched against is truncated, so catastrophic
# backtracking cannot run on unbounded input. ``validate_rule_definition``
# additionally rejects the common nested-quantifier ReDoS shape (``(a+)+``).
MAX_REGEX_PATTERN_LENGTH = 200
MAX_REGEX_INPUT_LENGTH = 1024
_QUANTIFIER_CHARS: frozenset[str] = frozenset("*+{")


def _is_unescaped(pattern: str, index: int) -> bool:
    """Return ``True`` when the character at ``index`` is not backslash-escaped."""
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and pattern[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 0


def _body_has_quantifier(body: str) -> bool:
    """Return ``True`` if ``body`` has a quantifier outside a character class."""
    in_class = False
    for i, char in enumerate(body):
        if not _is_unescaped(body, i):
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif not in_class and char in _QUANTIFIER_CHARS:
            return True
    return False


def _has_nested_quantifier(pattern: str) -> bool:
    """Heuristically flag catastrophic-backtracking patterns like ``(a+)+``.

    Detects a quantifier applied to a group whose body already contains a
    quantifier. This is the most common ReDoS shape; the check is deliberately
    conservative and may reject some safe-but-unusual patterns.
    """
    open_groups: list[int] = []
    for i, char in enumerate(pattern):
        if not _is_unescaped(pattern, i):
            continue
        if char == "(":
            open_groups.append(i)
        elif char == ")" and open_groups:
            start = open_groups.pop()
            after = pattern[i + 1 : i + 2]
            if after in _QUANTIFIER_CHARS and _body_has_quantifier(
                pattern[start + 1 : i]
            ):
                return True
    return False


def validate_rule_definition(
    operator: str,
    pattern: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
) -> None:
    """Raise ``ValueError`` if the operator/pattern/amount combination is invalid.

    Mirrors the ``ck_category_rules_definition`` check constraint and adds
    regex compilation and amount-range checks the database cannot express.
    """
    if operator == "amount_between":
        if amount_min is None and amount_max is None:
            raise ValueError(
                "amount_between rules require amount_min or amount_max"
            )
        if (
            amount_min is not None
            and amount_max is not None
            and amount_min > amount_max
        ):
            raise ValueError("amount_min must not be greater than amount_max")
        return
    if pattern is None or not pattern.strip():
        raise ValueError(f"{operator} rules require a non-empty pattern")
    if operator == "regex":
        if len(pattern) > MAX_REGEX_PATTERN_LENGTH:
            raise ValueError(
                "regex pattern must be at most "
                f"{MAX_REGEX_PATTERN_LENGTH} characters"
            )
        if _has_nested_quantifier(pattern):
            raise ValueError(
                "regex pattern has nested quantifiers that risk catastrophic "
                "backtracking; simplify the pattern"
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regular expression: {exc}") from exc


def _match_value(rule: CategoryRule, transaction: Transaction) -> str | None:
    return getattr(transaction, rule.match_field, None)


def _text_matches(operator: str, pattern: str, value: str) -> bool:
    haystack = value.lower()
    needle = pattern.lower()
    if operator == "contains":
        return needle in haystack
    if operator == "equals":
        return haystack == needle
    if operator == "starts_with":
        return haystack.startswith(needle)
    if operator == "regex":
        try:
            # Truncate the haystack so a pattern that slips past validation
            # cannot backtrack over unbounded input.
            return (
                re.search(
                    pattern, value[:MAX_REGEX_INPUT_LENGTH], re.IGNORECASE
                )
                is not None
            )
        except re.error:
            return False
    return False


def _amount_matches(rule: CategoryRule, amount: Decimal) -> bool:
    if rule.amount_min is None and rule.amount_max is None:
        return False
    if rule.amount_min is not None and amount < rule.amount_min:
        return False
    if rule.amount_max is not None and amount > rule.amount_max:
        return False
    return True


def rule_matches(rule: CategoryRule, transaction: Transaction) -> bool:
    """Return ``True`` when ``transaction`` satisfies ``rule``'s condition."""
    if rule.operator == "amount_between":
        return _amount_matches(rule, transaction.amount)
    value = _match_value(rule, transaction)
    if value is None or rule.pattern is None:
        return False
    return _text_matches(rule.operator, rule.pattern, value)


def find_matching_rule(
    rules: list[CategoryRule], transaction: Transaction
) -> CategoryRule | None:
    """Return the highest-priority active rule matching ``transaction``.

    Rules are ordered by explicit ``priority`` ascending, then by operator
    specificity (:data:`OPERATOR_PRIORITY`). The first match wins; returns
    ``None`` when no active rule matches.
    """
    ordered = sorted(
        (rule for rule in rules if rule.is_active),
        key=lambda rule: (rule.priority, OPERATOR_PRIORITY.get(rule.operator, 99)),
    )
    for rule in ordered:
        if rule_matches(rule, transaction):
            return rule
    return None
