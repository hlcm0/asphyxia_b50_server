from app.providers.maomani.service import build_b50, clear_lamp


def make_record(mid: int, difficulty: int, score: int, clear: int, volforce: int) -> list[str]:
    record = ["0"] * 12
    record[0] = str(mid)
    record[1] = str(difficulty)
    record[2] = str(score)
    record[4] = str(clear)
    record[11] = str(volforce)
    return record


def test_build_b50_sorts_by_volforce_score_mid_and_difficulty() -> None:
    b50 = build_b50(
        [
            make_record(2000, 4, 9_900_000, 5, 50_000),
            make_record(1000, 3, 10_000_000, 6, 50_000),
            make_record(1000, 2, 10_000_000, 4, 50_000),
            make_record(9999, 1, 8_000_000, 2, 60_000),
        ],
        "REFID",
    )

    cards = b50["cards"]
    assert [card["mid"] for card in cards] == [9999, 1000, 1000, 2000]
    assert [card["difficultyNum"] for card in cards] == [1, 2, 3, 4]
    assert b50["totalVf"] == "2.100"
    assert cards[0]["singleVf"] == "30.00"
    assert cards[0]["title"] == ""
    assert cards[0]["difficultyLabel"] == ""
    assert cards[0]["level"] == ""


def test_clear_lamp_matches_uploaded_b50_short_labels() -> None:
    assert [clear_lamp(value) for value in range(7)] == [
        "ND",
        "C",
        "EC",
        "HC",
        "MC",
        "UC",
        "PUC",
    ]
