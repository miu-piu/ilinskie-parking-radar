from scoring import choose


def row(number, price, group_name):
    return {
        "number": number,
        "current_price_rub": price,
        "start_price_rub": price,
        "group_name": group_name,
    }


def test_premium_when_gap_small():
    result = choose(
        [row(296, 1_500_000, "premium"), row(294, 1_380_000, "watch")],
        hard_cap=1_650_000,
        premium_gap=150_000,
        cheap_gap=300_000,
    )
    assert result.action == "ПРЕМИУМ"
    assert result.premium_number == 296


def test_cheap_when_gap_large():
    result = choose(
        [row(296, 1_638_000, "premium"), row(294, 1_300_000, "watch")],
        hard_cap=1_650_000,
        premium_gap=150_000,
        cheap_gap=300_000,
    )
    assert result.action == "ДЕШЁВОЕ"
    assert result.cheap_number == 294


def test_exit_when_everything_above_cap():
    result = choose(
        [row(170, 1_655_000, "premium"), row(294, 1_660_000, "watch")],
        hard_cap=1_650_000,
        premium_gap=150_000,
        cheap_gap=300_000,
    )
    assert result.action == "ВЫЙТИ"
