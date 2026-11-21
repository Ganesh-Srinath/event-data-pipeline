import os
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError

from clean_logs import validate, transform

DATA_DIR = Path(os.environ.get("DATA_DIR", "."))
INCOMING_DIR = DATA_DIR / "incoming"

client = MongoClient(
    os.environ.get("MONGO_URI", "mongodb://localhost:27017"),
    serverSelectionTimeoutMS=3000,
)

db = client["event_pipeline"]
raw_files = db["raw_files"]
cleaned_events = db["cleaned_events"]
audit = db["audit"]


def setup_indexes():
    # A unique index makes MongoDB itself refuse duplicates.
    raw_files.create_index([("file_hash", ASCENDING)], unique=True)
    cleaned_events.create_index([("event_id", ASCENDING)], unique=True)


def file_fingerprint(path):
    """Hash of the file's contents. Same contents -> same fingerprint, whatever the name."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def read_and_clean(path):
    """Validate and transform every record. Returns (total, cleaned_list, reject_reasons)."""
    seen_ids = set()
    cleaned = []
    reasons = {}
    total = 0

    def reject(reason):
        reasons[reason] = reasons.get(reason, 0) + 1

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                reject("invalid_json")
                continue

            reason = validate(event)
            if reason:
                reject(reason)
                continue

            if event["event_id"] in seen_ids:
                reject("duplicate_event_id")
                continue
            seen_ids.add(event["event_id"])

            cleaned.append(transform(event))

    return total, cleaned, reasons


def process_file(path):
    started = time.time()
    fingerprint = file_fingerprint(path)

    # Idempotency check: have we already finished this exact file?
    existing = raw_files.find_one({"file_hash": fingerprint})
    if existing and existing["status"] == "done":
        print(f"SKIP  {path.name} (already processed)")
        return

    # Record that the file arrived (only if this is the first attempt).
    if not existing:
        raw_files.insert_one({
            "file_hash": fingerprint,
            "file_name": path.name,
            "status": "processing",
            "arrived_at": datetime.now(timezone.utc),
        })

    total, cleaned, reasons = read_and_clean(path)

    # Save good events. The unique index on event_id blocks any repeats.
    inserted = 0
    already_in_db = 0
    if cleaned:
        try:
            result = cleaned_events.insert_many(cleaned, ordered=False)
            inserted = len(result.inserted_ids)
        except BulkWriteError as e:
            errors = e.details["writeErrors"]
            if any(err["code"] != 11000 for err in errors):  # 11000 = duplicate key
                raise
            inserted = e.details["nInserted"]
            already_in_db = len(errors)

    # Audit record: one summary per file.
    audit.insert_one({
        "file_name": path.name,
        "file_hash": fingerprint,
        "total_records": total,
        "cleaned_records": len(cleaned),
        "inserted_now": inserted,
        "already_in_db": already_in_db,
        "rejected_records": total - len(cleaned),
        "rejection_reasons": reasons,
        "duration_seconds": round(time.time() - started, 3),
        "processed_at": datetime.now(timezone.utc),
    })

    # Only now mark the file as finished.
    raw_files.update_one({"file_hash": fingerprint}, {"$set": {"status": "done"}})

    print(f"DONE  {path.name}: total={total}, cleaned={len(cleaned)}, "
          f"inserted={inserted}, rejected={total - len(cleaned)}")


def run_all():
    setup_indexes()
    for file_path in sorted(INCOMING_DIR.glob("*.jsonl")):
        process_file(file_path)


if __name__ == "__main__":
    run_all()