from scoring import choose, entry_price


def row(number, price, group_name, bid_count=0):
    return {
        "number": number,
        "current_price_rub": price,
        "start_price_rub": price,
        "group_name": group_name,
        "bid_count": bid_count,
        "status": "free",
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


def test_entry_price_adds_bid_step_after_first_bid():
    assert entry_price(row(170, 1_615_000, "premium", bid_count=0), 20_000) == 1_615_000
    assert entry_price(row(170, 1_615_000, "premium", bid_count=1), 20_000) == 1_635_000


def test_current_price_under_cap_can_still_be_too_late_to_enter():
    result = choose(
        [row(170, 1_635_000, "premium", bid_count=1), row(294, 1_400_000, "watch")],
        hard_cap=1_650_000,
        premium_gap=150_000,
        cheap_gap=300_000,
        bid_step=20_000,
    )
    assert result.action == "ДЕШЁВОЕ"
    assert result.premium_number is None
