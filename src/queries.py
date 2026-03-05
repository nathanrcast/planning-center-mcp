import math
import re
from datetime import datetime, timezone, timedelta

from pymongo.database import Database

CONFIRMED = ["C", "confirmed"]
DECLINED = ["D", "declined"]


def song_usage(db: Database, months: int = 3, service_type_ids: list[str] | None = None,
               start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    if start_date and end_date:
        cutoff, now = start_date, end_date
    else:
        now = datetime.now(timezone.utc).isoformat()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()

    match_filter = {"sort_date": {"$gte": cutoff, "$lte": now}}
    if service_type_ids:
        match_filter["service_type_id"] = {"$in": service_type_ids}

    pipeline = [
        {"$match": match_filter},
        {"$unwind": "$items"},
        {"$match": {"items.song_id": {"$ne": None}}},
        {"$group": {
            "_id": {"$toLower": "$items.title"},
            "title": {"$first": "$items.title"},
            "count": {"$sum": 1},
            "last_played": {"$max": "$sort_date"},
        }},
        {"$sort": {"count": -1}},
    ]
    results = list(db.plans.aggregate(pipeline))
    return [
        {
            "title": r["title"],
            "count": r["count"],
            "last_played": r["last_played"][:10] if r.get("last_played") else None,
        }
        for r in results
    ]


def volunteer_activity(db: Database, months: int = 3, service_type_ids: list[str] | None = None,
                       start_date: str | None = None, end_date: str | None = None,
                       team_names: list[str] | None = None) -> list[dict]:
    if start_date and end_date:
        cutoff, now = start_date, end_date
    else:
        now = datetime.now(timezone.utc).isoformat()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()

    match_filter = {"sort_date": {"$gte": cutoff, "$lte": now}}
    if service_type_ids:
        match_filter["service_type_id"] = {"$in": service_type_ids}

    team_match = {"team_members.status": {"$in": CONFIRMED}}
    if team_names:
        team_match["team_members.team_name"] = {"$in": team_names}

    pipeline = [
        {"$match": match_filter},
        {"$unwind": "$team_members"},
        {"$match": team_match},
        {"$group": {
            "_id": "$team_members.name",
            "count": {"$sum": 1},
            "teams": {"$addToSet": "$team_members.team_name"},
        }},
        {"$sort": {"count": -1}},
    ]
    results = list(db.plans.aggregate(pipeline))
    return [
        {
            "name": r["_id"],
            "teams": ", ".join(sorted(t for t in r["teams"] if t)),
            "count": r["count"],
        }
        for r in results
    ]


def team_names_list(db: Database) -> list[str]:
    return sorted(
        name for name in db.plans.distinct("team_members.team_name") if name
    )


def service_plans(db: Database, service_type_name: str, count: int = 5) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    plans = list(
        db.plans.find(
            {
                "service_type_name": {"$regex": re.escape(service_type_name), "$options": "i"},
                "sort_date": {"$lte": now},
            },
            sort=[("sort_date", -1)],
            limit=count,
        )
    )
    return [
        {
            "date": p.get("dates") or (p.get("sort_date", "?")[:10]),
            "title": p.get("title") or "Untitled",
            "items": [
                {
                    "title": i["title"],
                    "key_name": i.get("key_name"),
                }
                for i in p.get("items", []) if i.get("song_id")
            ],
            "team_members": [
                {
                    "name": m["name"],
                    "position_name": m.get("position_name"),
                    "status": m.get("status"),
                }
                for m in p.get("team_members", [])
            ],
        }
        for p in plans
    ]


def song_detail(db: Database, title: str) -> dict | None:
    song = db.songs.find_one(
        {"title": {"$regex": re.escape(title), "$options": "i"}}
    )
    if not song:
        return None

    song_id = song["_id"]
    schedule_pipeline = [
        {"$unwind": "$items"},
        {"$match": {"items.song_id": song_id}},
        {"$project": {
            "date": "$sort_date",
            "service_type_name": "$service_type_name",
        }},
        {"$sort": {"date": -1}},
    ]
    schedules = list(db.plans.aggregate(schedule_pipeline))

    return {
        "title": song["title"],
        "author": song.get("author"),
        "ccli_number": song.get("ccli_number"),
        "arrangements": [
            {
                "name": a["name"],
                "bpm": a.get("bpm"),
                "meter": a.get("meter"),
            }
            for a in song.get("arrangements", [])
        ],
        "schedules": [
            {
                "date": s["date"][:10] if s.get("date") else None,
                "service_type_name": s.get("service_type_name"),
            }
            for s in schedules
        ],
    }


def upcoming_services(db: Database, weeks: int = 4) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(weeks=weeks)).isoformat()

    plans = list(
        db.plans.find(
            {"sort_date": {"$gte": now, "$lte": future}},
            sort=[("sort_date", 1)],
        )
    )

    result = []
    for plan in plans:
        members = plan.get("team_members", [])
        confirmed = [m for m in members if m.get("status") in CONFIRMED]
        pending = [m for m in members if m.get("status") not in CONFIRMED + DECLINED]
        declined = [m for m in members if m.get("status") in DECLINED]

        result.append({
            "date": plan.get("dates") or (plan.get("sort_date", "?")[:10]),
            "service_type": plan.get("service_type_name", ""),
            "confirmed": [{"name": m["name"], "position": m.get("position_name", "?")} for m in confirmed],
            "pending": [{"name": m["name"], "position": m.get("position_name", "?")} for m in pending],
            "declined": [{"name": m["name"]} for m in declined],
        })
    return result


def service_types_list(db: Database) -> list[dict]:
    return [
        {"id": st["_id"], "name": st["name"]}
        for st in db.service_types.find()
    ]


def sync_status(db: Database) -> dict:
    meta = db.sync_meta.find_one({"_id": "last_sync"})
    return {"last_sync": meta["timestamp"] if meta else None}


# ── Prophecy queries ───────────────────────────────────────────


def _prophecy_doc(s: dict, include_email: bool = False) -> dict:
    doc = {
        "id": str(s["_id"]),
        "title": s["title"],
        "content": s["content"],
        "author_name": s.get("author_name", ""),
        "author_type": s.get("author_type", "congregation"),
        "tags": s.get("tags", []),
        "status": s.get("status", "pending"),
        "submitted_at": s.get("submitted_at"),
        "approved_at": s.get("approved_at"),
        "approved_by": s.get("approved_by"),
    }
    if include_email:
        doc["author_email"] = s.get("author_email", "")
    return doc


def list_prophecies(
    db: Database,
    status: str | None = None,
    tag: str | None = None,
    page: int = 1,
    per_page: int = 20,
    include_email: bool = False,
) -> dict:
    query: dict = {}
    if status:
        query["status"] = status
    if tag:
        query["tags"] = tag

    total = db.stories.count_documents(query)
    docs = list(
        db.stories.find(query)
        .sort("submitted_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return {
        "prophecies": [_prophecy_doc(d, include_email=include_email) for d in docs],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def get_prophecy(db: Database, prophecy_id: str, include_email: bool = False) -> dict | None:
    from bson import ObjectId

    try:
        doc = db.stories.find_one({"_id": ObjectId(prophecy_id)})
    except Exception:
        return None
    return _prophecy_doc(doc, include_email=include_email) if doc else None


def search_prophecies_keyword(
    db: Database,
    query: str,
    tag: str | None = None,
    status: str = "approved",
    include_email: bool = False,
) -> list[dict]:
    match: dict = {"$text": {"$search": query}, "status": status}
    if tag:
        match["tags"] = tag

    pipeline = [
        {"$match": match},
        {"$addFields": {"score": {"$meta": "textScore"}}},
        {"$sort": {"score": -1}},
        {"$limit": 50},
    ]
    return [_prophecy_doc(d, include_email=include_email) for d in db.stories.aggregate(pipeline)]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_prophecies_semantic(
    db: Database,
    query_embedding: list[float],
    top_k: int = 10,
    status: str = "approved",
    include_email: bool = False,
) -> list[dict]:
    docs = list(
        db.stories.find(
            {"status": status, "embedding": {"$exists": True, "$ne": None}},
            {"embedding": 1, "title": 1, "content": 1, "author_name": 1,
             "author_email": 1, "author_type": 1, "tags": 1, "status": 1,
             "submitted_at": 1, "approved_at": 1, "approved_by": 1},
        )
    )
    scored = []
    for d in docs:
        sim = _cosine_similarity(query_embedding, d["embedding"])
        scored.append((sim, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {**_prophecy_doc(d, include_email=include_email), "similarity": round(sim, 4)}
        for sim, d in scored[:top_k]
    ]


def prophecy_tags(db: Database) -> list[str]:
    return sorted(t for t in db.stories.distinct("tags") if t)
