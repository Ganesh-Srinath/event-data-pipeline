import os
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "."))
OUTPUT_DIR = DATA_DIR / "incoming"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EVENT_TYPES = ["view_product", "add_to_cart", "purchase"]
PRODUCTS = ["P101", "P102", "P103", "P104", "P105"]
USERS = [f"U{n}" for n in range(1, 51)]


def make_good_event(base_time):
    """Create one clean, correct event."""
    random_seconds = random.randint(0, 3599)
    return {
        "event_id": str(uuid.uuid4()),
        "user_id": random.choice(USERS),
        "event_type": random.choice(EVENT_TYPES),
        "product_id": random.choice(PRODUCTS),
        "price": round(random.uniform(100, 5000), 2),
        "timestamp": (base_time + timedelta(seconds=random_seconds)).isoformat(),
    }


def make_messy(event):
    """Break an event in one random way. Returns a list of events."""
    problem = random.choice(
        ["missing_field", "bad_date", "negative_price", "wrong_type", "duplicate"]
    )
    if problem == "missing_field":
        del event[random.choice(["user_id", "event_type", "product_id"])]
    elif problem == "bad_date":
        event["timestamp"] = random.choice(["not-a-date", "17/11/2026 10:30", ""])
    elif problem == "negative_price":
        event["price"] = -abs(event["price"])
    elif problem == "wrong_type":
        event["price"] = str(event["price"]) + " rupees"
    elif problem == "duplicate":
        return [event, event.copy()]
    return [event]


def generate_file(num_events=200, bad_rate=0.15):
    base_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    events = []
    for _ in range(num_events):
        event = make_good_event(base_time)
        if random.random() < bad_rate:
            events.extend(make_messy(event))
        else:
            events.append(event)

    filename = OUTPUT_DIR / f"logs_{base_time.strftime('%Y-%m-%d_%H')}.jsonl"
    with open(filename, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    print(f"Wrote {len(events)} events to {filename}")


if __name__ == "__main__":
    generate_file()