from pymongo import MongoClient, UpdateOne

client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)
db = client["event_pipeline"]


def count_type(name):
    """MongoDB expression: 1 if the event is this type, else 0."""
    return {"$sum": {"$cond": [{"$eq": ["$event_type", name]}, 1, 0]}}


def build_daily_summary():
    pipeline = [
        {"$group": {
            "_id": "$date",
            "total_events": {"$sum": 1},
            "views": count_type("view_product"),
            "add_to_carts": count_type("add_to_cart"),
            "purchases": count_type("purchase"),
            "revenue": {"$sum": {"$cond": [{"$eq": ["$event_type", "purchase"]}, "$price", 0]}},
            "users": {"$addToSet": "$user_id"},
        }},
        {"$project": {
            "_id": 0,
            "date": "$_id",
            "total_events": 1,
            "views": 1,
            "add_to_carts": 1,
            "purchases": 1,
            "revenue": {"$round": ["$revenue", 2]},
            "unique_users": {"$size": "$users"},
        }},
        {"$sort": {"date": 1}},
    ]
    rows = list(db["cleaned_events"].aggregate(pipeline))

    # Upsert: update the row for that date if it exists, otherwise create it.
    ops = [UpdateOne({"date": r["date"]}, {"$set": r}, upsert=True) for r in rows]
    if ops:
        db["daily_summary"].bulk_write(ops)
    return rows


def print_report():
    rows = build_daily_summary()

    print("\n=== DAILY SUMMARY ===")
    print(f"{'date':<12}{'events':>8}{'views':>8}{'carts':>8}{'buys':>8}{'revenue':>12}{'users':>8}")
    for r in rows:
        print(f"{r['date']:<12}{r['total_events']:>8}{r['views']:>8}{r['add_to_carts']:>8}"
              f"{r['purchases']:>8}{r['revenue']:>12.2f}{r['unique_users']:>8}")

    print("\n=== PIPELINE HEALTH ===")
    files = list(db["audit"].find())
    total = sum(a["total_records"] for a in files)
    rejected = sum(a["rejected_records"] for a in files)
    print(f"files processed : {len(files)}")
    print(f"total records   : {total}")
    print(f"rejected        : {rejected} ({rejected / total * 100:.1f}%)" if total else "rejected: 0")

    reasons = {}
    for a in files:
        for reason, count in a["rejection_reasons"].items():
            reasons[reason] = reasons.get(reason, 0) + count
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  - {reason}: {count}")
    print()


if __name__ == "__main__":
    print_report()