from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurrencySeed:
    code: str
    name: str
    symbol: str
    minor_units: int = 2


COMMON_CURRENCIES: tuple[CurrencySeed, ...] = (
    CurrencySeed(code="RUB", name="Russian Ruble", symbol="₽"),
    CurrencySeed(code="USD", name="US Dollar", symbol="$"),
    CurrencySeed(code="EUR", name="Euro", symbol="€"),
    CurrencySeed(code="GEL", name="Georgian Lari", symbol="₾"),
    CurrencySeed(code="KZT", name="Kazakhstani Tenge", symbol="₸"),
    CurrencySeed(code="TRY", name="Turkish Lira", symbol="₺"),
    CurrencySeed(code="AED", name="UAE Dirham", symbol="د.إ"),
)
