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
            "key_name": "$items.key_name",
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
                "key_name": s.get("key_name"),
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


def person_song_keys(db: Database, person_name: str,
                     role: str | None = None,
                     months: int | None = None) -> dict:
    member_filter: dict = {"name": {"$regex": re.escape(person_name), "$options": "i"}}
    if role:
        member_filter["position_name"] = {"$regex": re.escape(role), "$options": "i"}

    match: dict = {"team_members": {"$elemMatch": member_filter}}
    if months:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
        match["sort_date"] = {"$gte": cutoff}

    pipeline = [
        {"$match": match},
        {"$unwind": "$items"},
        {"$match": {
            "items.song_id": {"$ne": None},
            "items.key_name": {"$nin": [None, ""]},
        }},
        {"$group": {"_id": "$items.key_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
    ]
    keys = list(db.plans.aggregate(pipeline))
    return {"person": person_name, "role": role, "keys": keys}


def songs_not_played(db: Database, months: int = 6, min_total_plays: int = 2) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
    pipeline = [
        {"$unwind": "$items"},
        {"$match": {"items.song_id": {"$ne": None}}},
        {"$group": {
            "_id": "$items.song_id",
            "title": {"$first": "$items.title"},
            "total_plays": {"$sum": 1},
            "last_played": {"$max": "$sort_date"},
            "recent_plays": {"$sum": {"$cond": [{"$gte": ["$sort_date", cutoff]}, 1, 0]}},
        }},
        {"$match": {"total_plays": {"$gte": min_total_plays}, "recent_plays": 0}},
        {"$sort": {"last_played": -1}},
        {"$project": {"_id": 0, "title": 1, "total_plays": 1, "last_played": 1}},
    ]
    results = list(db.plans.aggregate(pipeline))
    return [
        {
            "title": r["title"],
            "total_plays": r["total_plays"],
            "last_played": r["last_played"][:10] if r.get("last_played") else None,
        }
        for r in results
    ]


def songs_by_key(db: Database, key_name: str) -> list[dict]:
    pipeline = [
        {"$unwind": "$items"},
        {"$match": {
            "items.song_id": {"$ne": None},
            "items.key_name": {"$regex": f"^{re.escape(key_name)}$", "$options": "i"},
        }},
        {"$group": {
            "_id": "$items.song_id",
            "title": {"$first": "$items.title"},
            "count": {"$sum": 1},
            "last_played": {"$max": "$sort_date"},
        }},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "title": 1, "count": 1, "last_played": 1}},
    ]
    results = list(db.plans.aggregate(pipeline))
    return [
        {
            "title": r["title"],
            "times_in_this_key": r["count"],
            "last_played": r["last_played"][:10] if r.get("last_played") else None,
        }
        for r in results
    ]


def person_song_preferences(db: Database, person_name: str,
                             role: str | None = None,
                             months: int | None = None) -> dict:
    member_filter: dict = {"name": {"$regex": re.escape(person_name), "$options": "i"}}
    if role:
        member_filter["position_name"] = {"$regex": re.escape(role), "$options": "i"}
    match: dict = {"team_members": {"$elemMatch": member_filter}}
    if months:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
        match["sort_date"] = {"$gte": cutoff}
    pipeline = [
        {"$match": match},
        {"$unwind": "$items"},
        {"$match": {"items.song_id": {"$ne": None}}},
        {"$group": {
            "_id": "$items.song_id",
            "title": {"$first": "$items.title"},
            "count": {"$sum": 1},
            "last_played": {"$max": "$sort_date"},
        }},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "title": 1, "count": 1, "last_played": 1}},
    ]
    results = list(db.plans.aggregate(pipeline))
    return {
        "person": person_name,
        "role": role,
        "songs": [
            {
                "title": r["title"],
                "count": r["count"],
                "last_played": r["last_played"][:10] if r.get("last_played") else None,
            }
            for r in results
        ],
    }


def songs_played_together(db: Database, title: str, limit: int = 10) -> dict | None:
    song = db.songs.find_one({"title": {"$regex": re.escape(title), "$options": "i"}})
    if not song:
        return None
    song_id = song["_id"]
    plan_ids = [p["_id"] for p in db.plans.find({"items.song_id": song_id}, {"_id": 1})]
    if not plan_ids:
        return {"title": song["title"], "co_songs": []}
    pipeline = [
        {"$match": {"_id": {"$in": plan_ids}}},
        {"$unwind": "$items"},
        {"$match": {"items.song_id": {"$nin": [None, song_id]}}},
        {"$group": {
            "_id": "$items.song_id",
            "title": {"$first": "$items.title"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "title": 1, "count": 1}},
    ]
    return {"title": song["title"], "co_songs": list(db.plans.aggregate(pipeline))}


def service_position_patterns(db: Database, position: str = "intro", limit: int = 15) -> list[dict]:
    pipeline = [
        {"$unwind": "$items"},
        {"$match": {
            "items.song_id": {"$ne": None},
            "items.service_position": {"$regex": re.escape(position), "$options": "i"},
        }},
        {"$group": {
            "_id": "$items.song_id",
            "title": {"$first": "$items.title"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "title": 1, "count": 1}},
    ]
    return list(db.plans.aggregate(pipeline))


def service_bpm_flow(db: Database, service_type_name: str | None = None, count: int = 10) -> list[dict]:
    match: dict = {}
    if service_type_name:
        match["service_type_name"] = {"$regex": re.escape(service_type_name), "$options": "i"}
    plans = list(db.plans.find(match, sort=[("sort_date", -1)], limit=count))
    result = []
    for plan in plans:
        songs_bpm = []
        for item in sorted(plan.get("items", []), key=lambda x: x.get("sequence") or 0):
            if not item.get("song_id"):
                continue
            song = db.songs.find_one({"_id": item["song_id"]}, {"arrangements": 1})
            bpm = next(
                (a["bpm"] for a in (song or {}).get("arrangements", []) if a.get("bpm")),
                None,
            )
            songs_bpm.append({"title": item["title"], "bpm": bpm, "key": item.get("key_name")})
        if songs_bpm:
            result.append({
                "date": plan["sort_date"][:10],
                "service_type": plan.get("service_type_name"),
                "songs": songs_bpm,
            })
    return result


def song_retirement_candidates(db: Database, active_months: int = 12,
                                inactive_months: int = 6, min_plays: int = 3) -> list[dict]:
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=inactive_months * 30)).isoformat()
    old_cutoff = (datetime.now(timezone.utc) - timedelta(days=active_months * 30)).isoformat()
    old_pipeline = [
        {"$match": {"sort_date": {"$gte": old_cutoff, "$lt": recent_cutoff}}},
        {"$unwind": "$items"},
        {"$match": {"items.song_id": {"$ne": None}}},
        {"$group": {
            "_id": "$items.song_id",
            "title": {"$first": "$items.title"},
            "old_plays": {"$sum": 1},
        }},
        {"$match": {"old_plays": {"$gte": min_plays}}},
    ]
    old_songs = {r["_id"]: r for r in db.plans.aggregate(old_pipeline)}
    recent_ids = {
        r["_id"] for r in db.plans.aggregate([
            {"$match": {"sort_date": {"$gte": recent_cutoff}}},
            {"$unwind": "$items"},
            {"$match": {"items.song_id": {"$ne": None}}},
            {"$group": {"_id": "$items.song_id"}},
        ])
    }
    candidates = [
        {"title": v["title"], "plays_before": v["old_plays"]}
        for k, v in old_songs.items()
        if k not in recent_ids
    ]
    candidates.sort(key=lambda x: x["plays_before"], reverse=True)
    return candidates


def volunteer_decline_patterns(db: Database, months: int = 3, min_declines: int = 2) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
    pipeline = [
        {"$match": {"sort_date": {"$gte": cutoff}}},
        {"$unwind": "$team_members"},
        {"$group": {
            "_id": "$team_members.name",
            "declined": {"$sum": {"$cond": [
                {"$in": ["$team_members.status", ["D", "declined"]]}, 1, 0,
            ]}},
            "confirmed": {"$sum": {"$cond": [
                {"$in": ["$team_members.status", ["C", "confirmed"]]}, 1, 0,
            ]}},
            "total": {"$sum": 1},
        }},
        {"$match": {"declined": {"$gte": min_declines}}},
        {"$sort": {"declined": -1}},
        {"$project": {
            "_id": 0,
            "name": "$_id",
            "declined": 1,
            "confirmed": 1,
            "total": 1,
            "decline_rate": {"$round": [{"$divide": ["$declined", "$total"]}, 2]},
        }},
    ]
    return list(db.plans.aggregate(pipeline))


def song_key_usage(db: Database, months: int = 6,
                   start_date: str | None = None,
                   end_date: str | None = None) -> list[dict]:
    if start_date and end_date:
        cutoff, now = start_date, end_date
    else:
        now = datetime.now(timezone.utc).isoformat()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()

    pipeline = [
        {"$match": {"sort_date": {"$gte": cutoff, "$lte": now}}},
        {"$unwind": "$items"},
        {"$match": {
            "items.song_id": {"$ne": None},
            "items.key_name": {"$nin": [None, ""]},
        }},
        {"$group": {"_id": "$items.key_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
    ]
    return list(db.plans.aggregate(pipeline))



# ── Prophecy queries (used by church-tools api.py, not exposed as MCP tools) ──


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
    embedding_docs = db.stories.find(
        {"status": status, "embedding": {"$exists": True, "$ne": None}},
        {"embedding": 1},
    )
    scored = []
    for d in embedding_docs:
        sim = _cosine_similarity(query_embedding, d["embedding"])
        scored.append((sim, d["_id"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    if not top:
        return []
    top_ids = [doc_id for _, doc_id in top]
    sim_by_id = {doc_id: sim for sim, doc_id in top}
    full_docs = {d["_id"]: d for d in db.stories.find({"_id": {"$in": top_ids}})}
    return [
        {**_prophecy_doc(full_docs[doc_id], include_email=include_email), "similarity": round(sim_by_id[doc_id], 4)}
        for doc_id in top_ids
        if doc_id in full_docs
    ]


def prophecy_tags(db: Database) -> list[str]:
    return sorted(t for t in db.stories.distinct("tags") if t)
