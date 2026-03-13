import logging
import threading
import time
from datetime import datetime, timezone

from pymongo.database import Database
from pypco import PCO

log = logging.getLogger(__name__)


class SyncManager:
    def __init__(self, db: Database, pco: PCO):
        self.db = db
        self.pco = pco
        self._lock = threading.Lock()

    def sync_all(self, full: bool = False) -> dict:
        if not self._lock.acquire(blocking=False):
            return {"error": "A sync is already in progress. Try again later."}
        try:
            return self._sync_all(full=full)
        finally:
            self._lock.release()

    def _sync_all(self, full: bool = False) -> dict:
        start = time.time()
        last_sync = None if full else self.get_last_sync()
        stats = {"mode": "full" if last_sync is None else "incremental"}
        errors = []
        for phase, fn in [
            ("service_types", self._sync_service_types),
            ("plans", lambda: self._sync_plans(since=last_sync)),
            ("songs", lambda: self._sync_songs(since=last_sync)),
            ("people", self._sync_people),
        ]:
            try:
                stats[phase] = fn()
            except Exception as e:
                log.exception("Sync phase '%s' failed", phase)
                stats[phase] = 0
                errors.append(f"{phase}: {e}")
        self.db.sync_meta.update_one(
            {"_id": "last_sync"},
            {"$set": {"timestamp": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        stats["duration_seconds"] = round(time.time() - start, 1)
        if errors:
            stats["errors"] = errors
        return stats

    def _sync_service_types(self) -> int:
        count = 0
        for st in self.pco.iterate("/services/v2/service_types"):
            self.db.service_types.update_one(
                {"_id": st["data"]["id"]},
                {"$set": {
                    "name": st["data"]["attributes"]["name"],
                    "frequency": st["data"]["attributes"].get("frequency"),
                    "last_plan_from": st["data"]["attributes"].get("last_plan_from"),
                    "raw_attributes": st["data"]["attributes"],
                }},
                upsert=True,
            )
            count += 1
        return count

    def _fetch_teams_for_service_type(self, st_id: str) -> dict:
        teams = {}
        for team in self.pco.iterate(f"/services/v2/service_types/{st_id}/teams"):
            teams[team["data"]["id"]] = team["data"]["attributes"]["name"]
        return teams

    def _sync_plans(self, since: str | None = None) -> int:
        count = 0
        for st in self.db.service_types.find():
            st_id = st["_id"]
            teams_map = self._fetch_teams_for_service_type(st_id)
            params = {}
            if since:
                params["filter"] = "updated_after"
                params["updated_after"] = since
            for plan in self.pco.iterate(
                f"/services/v2/service_types/{st_id}/plans", **params
            ):
                plan_id = plan["data"]["id"]
                attrs = plan["data"]["attributes"]

                items = self._fetch_plan_items(plan_id)
                team_members = self._fetch_plan_team_members(plan_id, teams_map)

                self.db.plans.update_one(
                    {"_id": plan_id},
                    {"$set": {
                        "service_type_id": st_id,
                        "service_type_name": st["name"],
                        "title": attrs.get("title"),
                        "dates": attrs.get("dates"),
                        "sort_date": attrs.get("sort_date"),
                        "series_title": attrs.get("series_title"),
                        "created_at": attrs.get("created_at"),
                        "updated_at": attrs.get("updated_at"),
                        "items": items,
                        "team_members": team_members,
                        "raw_attributes": attrs,
                    }},
                    upsert=True,
                )
                count += 1
        return count

    def _fetch_plan_items(self, plan_id: str) -> list:
        items = []
        for item in self.pco.iterate(f"/services/v2/plans/{plan_id}/items"):
            attrs = item["data"]["attributes"]
            song_rel = item["data"].get("relationships", {}).get("song", {}).get("data")
            song_id = song_rel["id"] if song_rel else None
            items.append({
                "id": item["data"]["id"],
                "title": attrs.get("title"),
                "item_type": attrs.get("item_type"),
                "song_id": song_id,
                "sequence": attrs.get("sequence"),
                "service_position": attrs.get("service_position"),
                "key_name": attrs.get("key_name"),
                "length": attrs.get("length"),
            })
        return items

    def _fetch_plan_team_members(self, plan_id: str, teams_map: dict) -> list:
        members = []
        for tm in self.pco.iterate(f"/services/v2/plans/{plan_id}/team_members"):
            attrs = tm["data"]["attributes"]
            team_rel = tm["data"].get("relationships", {}).get("team", {}).get("data")
            team_id = team_rel["id"] if team_rel else None
            members.append({
                "id": tm["data"]["id"],
                "name": attrs.get("name"),
                "status": attrs.get("status"),
                "team_name": teams_map.get(team_id) if team_id else None,
                "position_name": attrs.get("team_position_name"),
            })
        return members

    def _sync_songs(self, since: str | None = None) -> int:
        count = 0
        params = {}
        if since:
            params["filter"] = "updated_after"
            params["updated_after"] = since
        for song in self.pco.iterate("/services/v2/songs", **params):
            song_id = song["data"]["id"]
            attrs = song["data"]["attributes"]

            arrangements = self._fetch_song_arrangements(song_id)
            schedules = self._fetch_song_schedules(song_id)

            self.db.songs.update_one(
                {"_id": song_id},
                {"$set": {
                    "title": attrs.get("title"),
                    "author": attrs.get("author"),
                    "ccli_number": attrs.get("ccli_number"),
                    "copyright": attrs.get("copyright"),
                    "created_at": attrs.get("created_at"),
                    "updated_at": attrs.get("updated_at"),
                    "last_scheduled_at": attrs.get("last_scheduled_at"),
                    "arrangements": arrangements,
                    "schedules": schedules,
                    "raw_attributes": attrs,
                }},
                upsert=True,
            )
            count += 1
        return count

    def _fetch_song_arrangements(self, song_id: str) -> list:
        arrangements = []
        for arr in self.pco.iterate(f"/services/v2/songs/{song_id}/arrangements"):
            attrs = arr["data"]["attributes"]
            arrangements.append({
                "id": arr["data"]["id"],
                "name": attrs.get("name"),
                "bpm": attrs.get("bpm"),
                "meter": attrs.get("meter"),
                "length": attrs.get("length"),
                "has_chords": attrs.get("has_chords"),
            })
        return arrangements

    def _fetch_song_schedules(self, song_id: str) -> list:
        schedules = []
        for sched in self.pco.iterate(
            f"/services/v2/songs/{song_id}/song_schedules",
            order="-plan_sort_date",
        ):
            attrs = sched["data"]["attributes"]
            schedules.append({
                "id": sched["data"]["id"],
                "plan_sort_date": attrs.get("plan_sort_date"),
                "service_type_name": attrs.get("service_type_name"),
                "plan_dates": attrs.get("plan_dates"),
            })
        return schedules

    def _sync_people(self) -> int:
        count = 0
        seen_ids = set()
        for plan in self.db.plans.find({"team_members": {"$ne": []}}):
            for tm in plan.get("team_members", []):
                person_id = tm["id"]
                if person_id in seen_ids:
                    continue
                seen_ids.add(person_id)
                self.db.people.update_one(
                    {"_id": person_id},
                    {"$set": {
                        "name": tm["name"],
                    }},
                    upsert=True,
                )
                count += 1
        return count

    def get_last_sync(self) -> str | None:
        meta = self.db.sync_meta.find_one({"_id": "last_sync"})
        return meta["timestamp"] if meta else None
