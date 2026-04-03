from pymongo.database import Database

from planning_center_mcp.llm import embed
from planning_center_mcp.queries import (
    song_usage,
    song_key_usage,
    person_song_keys,
    songs_not_played,
    songs_by_key,
    person_song_preferences,
    songs_played_together,
    service_position_patterns,
    service_bpm_flow,
    song_retirement_candidates,
    volunteer_decline_patterns,
    volunteer_activity,
    service_plans,
    song_detail,
    upcoming_services,
    search_prophecies_keyword,
    search_prophecies_semantic,
    get_prophecy,
    team_names_list,
    sync_status,
    list_prophecies,
    prophecy_tags,
)
from planning_center_mcp.sync import SyncManager


def register_report_tools(mcp: object, db: Database, sync_mgr: SyncManager):

    @mcp.tool
    def sync_pco_data(full: bool = False) -> dict:
        """Sync PCO data. Incremental by default, full=True for complete re-sync."""
        return sync_mgr.sync_all(full=full)

    @mcp.tool
    def song_usage_report(
        months: int = 3,
        service_type_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 25,
    ) -> dict:
        """Ranked song usage. Filter by service_type_ids, start_date/end_date (ISO), or months."""
        results = song_usage(db, months, service_type_ids=service_type_ids,
                             start_date=start_date, end_date=end_date)
        period = f"{start_date} to {end_date}" if start_date and end_date else f"last {months} months"
        return {"period": period, "songs": results[:limit], "total": len(results)}

    @mcp.tool
    def volunteer_activity_report(
        months: int = 3,
        service_type_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        team_names: list[str] | None = None,
        limit: int = 25,
    ) -> dict:
        """Ranked volunteer frequency. Filter by service_type_ids, dates, or team_names."""
        results = volunteer_activity(db, months, service_type_ids=service_type_ids,
                                     start_date=start_date, end_date=end_date,
                                     team_names=team_names)
        period = f"{start_date} to {end_date}" if start_date and end_date else f"last {months} months"
        return {"period": period, "volunteers": results[:limit], "total": len(results)}

    @mcp.tool
    def service_plan_report(service_type_name: str, count: int = 5) -> list:
        """Recent plans with setlists and teams for a service type."""
        return service_plans(db, service_type_name, count)

    @mcp.tool
    def song_detail_report(title: str) -> dict | str:
        """Full song details with arrangements and schedule history."""
        result = song_detail(db, title)
        if not result:
            return f"No song found matching '{title}'."
        return result

    @mcp.tool
    def person_song_keys_report(
        person_name: str,
        role: str | None = None,
        months: int | None = None,
    ) -> dict:
        """Keys used in plans where a specific person served, ranked by frequency.
        Optionally filter by role (e.g. 'Guitar', 'Worship Leader') and number of months.
        Use this for questions like 'what keys does [name] play in?' or
        'what keys are used when [name] is worship leader?'"""
        return person_song_keys(db, person_name, role=role, months=months)

    @mcp.tool
    def person_song_preferences_report(
        person_name: str,
        role: str | None = None,
        months: int | None = None,
    ) -> dict:
        """Songs played in plans where a specific person served, ranked by frequency.
        Optionally filter by role and months. Use for 'what songs does [name] usually pick?'
        For keys instead of song titles, use person_song_keys_report."""
        return person_song_preferences(db, person_name, role=role, months=months)

    @mcp.tool
    def songs_not_played_report(months: int = 6, min_total_plays: int = 2) -> list:
        """Songs with at least min_total_plays all-time that haven't been played in the last N months.
        Sorted by most recently played before the cutoff. Useful for rediscovering neglected songs."""
        return songs_not_played(db, months=months, min_total_plays=min_total_plays)

    @mcp.tool
    def songs_by_key_report(key_name: str) -> list:
        """All songs that have been played in a specific key (e.g. 'G', 'Bb', 'C#'),
        ranked by how many times they've been played in that key.
        Useful for 'what songs can we do in G?' or setlist planning by key."""
        return songs_by_key(db, key_name)

    @mcp.tool
    def songs_played_together_report(title: str, limit: int = 10) -> dict | str:
        """Songs most frequently paired with a given song in the same service plan.
        Useful for 'what songs go well with [title]?' or building setlists with consistent flow."""
        result = songs_played_together(db, title, limit=limit)
        if result is None:
            return f"No song found matching '{title}'."
        return result

    @mcp.tool
    def service_position_report(position: str = "intro", limit: int = 15) -> list:
        """Songs most commonly used in a given service position, ranked by frequency.
        Common positions: 'intro', 'outro', 'middle'. Use for 'what do we usually open with?'"""
        return service_position_patterns(db, position=position, limit=limit)

    @mcp.tool
    def service_bpm_flow_report(service_type_name: str | None = None, count: int = 10) -> list:
        """BPM and key progression for recent service plans, in song order.
        Note: BPM data may be sparse if arrangements haven't been filled in PCO.
        Useful for 'what's our typical tempo flow?' or energy arc analysis."""
        return service_bpm_flow(db, service_type_name=service_type_name, count=count)

    @mcp.tool
    def song_retirement_report(
        active_months: int = 12,
        inactive_months: int = 6,
        min_plays: int = 3,
    ) -> list:
        """Songs played frequently in the older window (active_months ago) but not used recently
        (within inactive_months). Sorted by former play count. Useful for identifying songs
        that have quietly fallen off the rotation."""
        return song_retirement_candidates(db, active_months=active_months,
                                          inactive_months=inactive_months, min_plays=min_plays)

    @mcp.tool
    def volunteer_decline_report(months: int = 3, min_declines: int = 2) -> list:
        """Volunteers with the most declined service requests in the last N months,
        including their decline rate. Useful for 'who has been declining a lot lately?'"""
        return volunteer_decline_patterns(db, months=months, min_declines=min_declines)

    @mcp.tool
    def song_key_usage_report(
        months: int = 6,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Aggregate key usage across all songs in a time period, ranked by frequency.
        Use this to answer questions like 'what keys are used most often?' or
        'what is the most common worship key?'. Filter by months or ISO start_date/end_date."""
        results = song_key_usage(db, months=months, start_date=start_date, end_date=end_date)
        period = f"{start_date} to {end_date}" if start_date and end_date else f"last {months} months"
        if not results:
            return {"period": period, "keys": [], "total": 0}
        return {"period": period, "keys": results, "total": sum(r["count"] for r in results)}

    @mcp.tool
    def upcoming_services_report(weeks: int = 4) -> list:
        """Upcoming plans with confirmed/pending/declined team members."""
        return upcoming_services(db, weeks)

    @mcp.tool
    def search_prophecies(query: str, semantic: bool = False) -> list:
        """Search prophecies by keyword or semantic similarity."""
        if semantic:
            query_embedding = embed(query)
            if not query_embedding:
                return [{"error": "Embedding service unavailable. Try keyword search."}]
            return search_prophecies_semantic(db, query_embedding, top_k=10)
        return search_prophecies_keyword(db, query)

    @mcp.tool
    def get_prophecy_detail(prophecy_id: str) -> dict | str:
        """Full text of a prophecy by ID."""
        result = get_prophecy(db, prophecy_id)
        if not result:
            return f"No prophecy found with ID '{prophecy_id}'."
        return result

    @mcp.tool
    def get_team_names() -> list[str]:
        """All team names from synced data. Use for volunteer_activity_report filtering."""
        return team_names_list(db)

    @mcp.tool
    def get_sync_status() -> dict:
        """When the last data sync occurred."""
        return sync_status(db)

    @mcp.tool
    def list_prophecies_report(
        status: str | None = None,
        tag: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """Browse prophecies. Filter by status (approved/pending) or tag."""
        return list_prophecies(db, status=status, tag=tag, page=page, per_page=per_page)

    @mcp.tool
    def get_prophecy_tags() -> list[str]:
        """All tags used across prophecies."""
        return prophecy_tags(db)
