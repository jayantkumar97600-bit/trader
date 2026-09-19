
from app.analysis.invalidation import validate_invalidation


def test_valid_long():
    result = validate_invalidation(
        direction="LONG",
        entry=4400,
        stop_loss=4385,
        current_price=4400,
    )

    assert result["valid"] is True
    assert result["status"] == "VALID"

    print("PASS: Valid LONG stop-loss")


def test_valid_short():
    result = validate_invalidation(
        direction="SHORT",
        entry=4415,
        stop_loss=4430,
        current_price=4415,
    )

    assert result["valid"] is True
    assert result["status"] == "VALID"

    print("PASS: Valid SHORT stop-loss")


def test_invalid_long_stop():
    result = validate_invalidation(
        direction="LONG",
        entry=4400,
        stop_loss=4410,
    )

    assert result["valid"] is False
    assert result["status"] == "INVALID"

    print("PASS: Invalid LONG stop-loss rejected")


def test_invalid_short_stop():
    result = validate_invalidation(
        direction="SHORT",
        entry=4415,
        stop_loss=4400,
    )

    assert result["valid"] is False
    assert result["status"] == "INVALID"

    print("PASS: Invalid SHORT stop-loss rejected")


def test_triggered_long_stop():
    result = validate_invalidation(
        direction="LONG",
        entry=4400,
        stop_loss=4385,
        current_price=4380,
    )

    assert result["status"] == "TRIGGERED"
    assert result["valid"] is False

    print("PASS: LONG stop-loss trigger detected")


def test_triggered_short_stop():
    result = validate_invalidation(
        direction="SHORT",
        entry=4415,
        stop_loss=4430,
        current_price=4435,
    )

    assert result["status"] == "TRIGGERED"
    assert result["valid"] is False

    print("PASS: SHORT stop-loss trigger detected")


if __name__ == "__main__":
    test_valid_long()
    test_valid_short()
    test_invalid_long_stop()
    test_invalid_short_stop()
    test_triggered_long_stop()
    test_triggered_short_stop()

    print("All invalidation tests passed.")