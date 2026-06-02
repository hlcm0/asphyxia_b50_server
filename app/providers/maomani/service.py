from datetime import UTC, datetime
from typing import Any

from app.providers.maomani.client import MaomaniClient


SDVX_VERSION = 7


def fetch_b50_by_card(card_no: str, client: MaomaniClient | None = None) -> dict[str, Any]:
    client = client or MaomaniClient()
    refid = client.get_refid(card_no)
    records = client.get_scores(refid)
    return build_b50(records, refid)


def build_b50(records: list[list[str]], refid: str) -> dict[str, Any]:
    score_records = [parse_record(record) for record in records if len(record) > 11]
    score_records.sort(
        key=lambda record: (
            -record["volforce"],
            -record["score"],
            record["mid"],
            record["difficultyNum"],
        )
    )

    top_records = score_records[:50]
    total_vf = sum(record["volforce"] for record in top_records) / 1000
    cards = [
        {
            "rank": index,
            "mid": record["mid"],
            "difficultyNum": record["difficultyNum"],
            "title": "",
            "difficultyLabel": "",
            "level": "",
            "score": record["score"],
            "clearLamp": clear_lamp(record["clear"]),
            "singleVf": f"{record['volforce'] / 20:.2f}",
        }
        for index, record in enumerate(top_records, start=1)
    ]

    return {
        "schemaVersion": 2,
        "source": "maomani",
        "game": "sdvx",
        "version": SDVX_VERSION,
        "player": {
            "refid": refid,
            "name": "",
            "sdvxId": 0,
            "scoreCount": len(score_records),
        },
        "totalVf": f"{total_vf:.3f}",
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "cards": cards,
    }


def parse_record(record: list[str]) -> dict[str, int]:
    return {
        "mid": int(record[0]),
        "difficultyNum": int(record[1]),
        "score": int(record[2]),
        "clear": int(record[4]),
        "volforce": int(record[11]) // 100,
    }


def clear_lamp(clear: int) -> str:
    return {
        1: "C",
        2: "EC",
        3: "HC",
        4: "MC",
        5: "UC",
        6: "PUC",
    }.get(clear, "ND")
