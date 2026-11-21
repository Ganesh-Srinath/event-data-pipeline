import os
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "."))
INCOMING_DIR = DATA_DIR / "incoming"
CLEANED_DIR = DATA_DIR / "cleaned"
REJECTED_DIR = DATA_DIR / "rejected"
CLEANED_DIR.mkdir(parents=True, exist_ok=True)
REJECTED_DIR.mkdir(parents=True, exist_ok=True) 

REQUIRED_FIELDS = ["event_id", "user_id", "event_type", "product_id", "price", "timestamp"]
VALID_EVENT_TYPES = {"view_product", "add_to_cart", "purchase"}


def validate(event):
    """Return None if the record is fine, otherwise a short reason why it's bad."""
    if not isinstance(event, dict):
        return "not_a_json_object"

    for field in REQUIRED_FIELDS:
        if field not in event or event[field] in (None, ""):
            return f"missing_field:{field}"

    if event["event_type"] not in VALID_EVENT_TYPES:
        return "invalid_event_type"

    price = event["price"]
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return "price_not_a_number"
    if price < 0:
        return "negative_price"

    try:
        datetime.fromisoformat(event["timestamp"])
    except (ValueError, TypeError):
        return "bad_timestamp"

    return None


def transform(event):
    """Clean small issues and add a useful extra field."""
    for key, value in event.items():
        if isinstance(value, str):
            event[key] = value.strip()
    event["price"] = round(event["price"], 2)
    event["date"] = event["timestamp"][:10]  # e.g. "2026-11-19"
    return event


def process_file(path):
    seen_ids = set()
    cleaned = []
    rejected = []
    total = 0

    with open(path) as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total += 1

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                rejected.append({"line": line_number, "reason": "invalid_json", "raw": line})
                continue

            reason = validate(event)
            if reason:
                rejected.append({"line": line_number, "reason": reason, "record": event})
                continue

            if event["event_id"] in seen_ids:
                rejected.append({"line": line_number, "reason": "duplicate_event_id", "record": event})
                continue
            seen_ids.add(event["event_id"])

            cleaned.append(transform(event))

    with open(CLEANED_DIR / path.name, "w") as f:
        for event in cleaned:
            f.write(json.dumps(event) + "\n")

    with open(REJECTED_DIR / path.name, "w") as f:
        for item in rejected:
            f.write(json.dumps(item) + "\n")

    reasons = {}
    for item in rejected:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1

    print(f"\n{path.name}")
    print(f"  total records : {total}")
    print(f"  cleaned       : {len(cleaned)}")
    print(f"  rejected      : {len(rejected)} ({len(rejected) / total * 100:.1f}%)")
    for reason, count in sorted(reasons.items()):
        print(f"    - {reason}: {count}")


if __name__ == "__main__":
    for file_path in sorted(INCOMING_DIR.glob("*.jsonl")):
        process_file(file_path)