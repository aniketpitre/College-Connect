import pytest

from app.core.money import amount_in_words, format_inr, group_indian, to_paise


def test_to_paise():
    assert to_paise("12500") == 1_250_000
    assert to_paise("1,25,000.50") == 12_500_050
    assert to_paise("Rs. 99.9") == 9990
    assert to_paise("₹ 10") == 1000
    assert to_paise(15) == 1500
    for bad in ("abc", "10.555", ""):
        with pytest.raises(ValueError):
            to_paise(bad)


def test_formatting():
    assert group_indian(1234567) == "12,34,567"
    assert group_indian(999) == "999"
    assert group_indian(100000) == "1,00,000"
    assert format_inr(125_000_050) == "Rs. 12,50,000.50"
    assert format_inr(-5000) == "-Rs. 50.00"


def test_amount_in_words():
    assert amount_in_words(125_050) == "Rupees One Thousand Two Hundred Fifty and Fifty Paise Only"
    assert amount_in_words(2_53_45_000 * 100) == "Rupees Two Crore Fifty Three Lakh Forty Five Thousand Only"
    assert amount_in_words(1_00_000 * 100) == "Rupees One Lakh Only"
    assert amount_in_words(0) == "Rupees Zero Only"
    assert amount_in_words(115_00_00_000 * 100) == "Rupees One Hundred Fifteen Crore Only"
