"""
Money is integer paise everywhere (spec §3.2). These helpers turn user input into paise and
paise into the text printed on receipts. Never use floats for amounts.
"""

import re
from decimal import Decimal, InvalidOperation

_ONES = (
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def to_paise(value: str | int) -> int:
    """'1,25,000.50' or '1250' (rupees) → paise. Rejects more than 2 decimal places."""
    if isinstance(value, int):
        return value * 100
    text = re.sub(r"[,\s₹]|^Rs\.?", "", str(value).strip(), flags=re.IGNORECASE)
    try:
        amount = Decimal(text)
    except InvalidOperation as e:
        raise ValueError("Enter an amount like 12500 or 12,500.50.") from e
    if amount.as_tuple().exponent < -2:  # type: ignore[operator]
        raise ValueError("Use at most 2 decimal places.")
    return int(amount * 100)


def group_indian(rupees: int) -> str:
    """1234567 → '12,34,567' (Indian digit grouping)."""
    s = str(abs(rupees))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1]
        s = f"{head},{tail}"
    return ("-" if rupees < 0 else "") + s


def format_inr(paise: int, symbol: str = "Rs. ") -> str:
    """125000050 → 'Rs. 12,50,000.50'."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    return f"{sign}{symbol}{group_indian(rupees)}.{p:02d}"


def _below_hundred(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else ""))


def _below_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if rest:
        parts.append(_below_hundred(rest))
    return " ".join(parts)


def _words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if n >= size:
            count, n = divmod(n, size)
            parts.append(f"{_words(count) if count >= 100 and size == 10_000_000 else _below_thousand(count)} {name}")
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def amount_in_words(paise: int) -> str:
    """125050 → 'Rupees One Thousand Two Hundred Fifty and Fifty Paise Only' (Indian system)."""
    rupees, p = divmod(abs(paise), 100)
    text = f"Rupees {_words(rupees)}"
    if p:
        text += f" and {_below_hundred(p)} Paise"
    return text + " Only"
