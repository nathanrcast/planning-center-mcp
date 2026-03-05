from pymongo.database import Database
from pypco import PCO

from src.llm import embed, summarize
from src.queries import (
    song_usage,
    volunteer_activity,
    service_plans,
    song_detail,
    upcoming_services,
    search_prophecies_keyword,
    search_prophecies_semantic,
    get_prophecy,
)
from src.sync import SyncManager


def register_report_tools(mcp: object, db: Database, pco: PCO):
    sync_mgr = SyncManager(db, pco)

    @mcp.tool
    def sync_pco_data() -> str:
        """Sync all Planning Center data into the local cache.

        Pulls service types, plans (with items and team members), songs
        (with arrangements and schedules), and people. Run this before
        reports if data might be stale.
        """
        stats = sync_mgr.sync_all()
        lines = ["**PCO Sync Complete**", ""]
        for key, val in stats.items():
            lines.append(f"- {key}: {val}")
        last = sync_mgr.get_last_sync()
        if last:
            lines.append(f"\nLast sync: {last}")
        return "\n".join(lines)

    @mcp.tool
    def song_usage_report(months: int = 3) -> str:
        """Get a ranked report of song usage across all service types.

        Args:
            months: How many months back to look (default 3).
        """
        results = song_usage(db, months)

        if not results:
            return f"No songs played in the last {months} months."

        lines = [f"## Song Usage — Last {months} Months", ""]
        lines.append("| # | Song | Times Played | Last Played |")
        lines.append("|---|------|-------------|-------------|")
        for i, r in enumerate(results, 1):
            last = r["last_played"] or "?"
            lines.append(f"| {i} | {r['title']} | {r['count']} | {last} |")

        report = "\n".join(lines)
        summary = summarize(report, "song usage")
        if summary:
            report = f"*{summary}*\n\n{report}"
        return report

    @mcp.tool
    def volunteer_activity_report(months: int = 3) -> str:
        """Get a ranked report of volunteer service frequency.

        Args:
            months: How many months back to look (default 3).
        """
        results = volunteer_activity(db, months)

        if not results:
            return f"No confirmed volunteers in the last {months} months."

        lines = [f"## Volunteer Activity — Last {months} Months", ""]
        lines.append("| # | Name | Teams | Times Served |")
        lines.append("|---|------|-------|-------------|")
        for i, r in enumerate(results, 1):
            lines.append(f"| {i} | {r['name']} | {r['teams']} | {r['count']} |")

        report = "\n".join(lines)
        summary = summarize(report, "volunteer activity")
        if summary:
            report = f"*{summary}*\n\n{report}"
        return report

    @mcp.tool
    def service_plan_report(service_type_name: str, count: int = 5) -> str:
        """Get the latest plans for a service type with setlists and teams.

        Args:
            service_type_name: Name of the service type (e.g. "Sunday Morning").
            count: Number of recent plans to return (default 5).
        """
        plans = service_plans(db, service_type_name, count)

        if not plans:
            return f"No plans found for '{service_type_name}'."

        lines = [f"## Recent Plans — {service_type_name}", ""]
        for plan in plans:
            lines.append(f"### {plan['date']} — {plan['title']}")

            if plan["items"]:
                lines.append("**Songs:**")
                for s in plan["items"]:
                    key = f" ({s['key_name']})" if s.get("key_name") else ""
                    lines.append(f"- {s['title']}{key}")

            if plan["team_members"]:
                lines.append("**Team:**")
                for m in plan["team_members"]:
                    pos = f" — {m['position_name']}" if m.get("position_name") else ""
                    status = f" [{m['status']}]" if m.get("status") else ""
                    lines.append(f"- {m['name']}{pos}{status}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool
    def song_detail_report(title: str) -> str:
        """Get full details for a song including arrangements and schedule history.

        Args:
            title: Song title (case-insensitive search).
        """
        result = song_detail(db, title)
        if not result:
            return f"No song found matching '{title}'."

        lines = [f"## {result['title']}"]
        if result.get("author"):
            lines.append(f"**Author:** {result['author']}")
        if result.get("ccli_number"):
            lines.append(f"**CCLI:** {result['ccli_number']}")
        lines.append("")

        if result["arrangements"]:
            lines.append("### Arrangements")
            for a in result["arrangements"]:
                parts = [a["name"]]
                if a.get("bpm"):
                    parts.append(f"{a['bpm']} BPM")
                if a.get("meter"):
                    parts.append(a["meter"])
                lines.append(f"- {' | '.join(parts)}")
            lines.append("")

        schedules = result["schedules"]
        if schedules:
            lines.append(f"### Schedule History ({len(schedules)} times)")
            lines.append("| Date | Service Type |")
            lines.append("|------|-------------|")
            for s in schedules[:20]:
                date = s["date"] or "?"
                stype = s.get("service_type_name", "?")
                lines.append(f"| {date} | {stype} |")
            if len(schedules) > 20:
                lines.append(f"\n*...and {len(schedules) - 20} more*")

        return "\n".join(lines)

    @mcp.tool
    def upcoming_services_report(weeks: int = 4) -> str:
        """Get upcoming service plans with assigned teams and any gaps.

        Args:
            weeks: How many weeks ahead to look (default 4).
        """
        plans = upcoming_services(db, weeks)

        if not plans:
            return f"No upcoming plans in the next {weeks} weeks."

        lines = [f"## Upcoming Services — Next {weeks} Weeks", ""]
        for plan in plans:
            lines.append(f"### {plan['date']} — {plan['service_type']}")

            if plan["confirmed"]:
                lines.append(
                    f"**Confirmed ({len(plan['confirmed'])}):** "
                    + ", ".join(f"{m['name']} ({m['position']})" for m in plan["confirmed"])
                )
            if plan["pending"]:
                lines.append(
                    f"**Pending ({len(plan['pending'])}):** "
                    + ", ".join(f"{m['name']} ({m['position']})" for m in plan["pending"])
                )
            if plan["declined"]:
                lines.append(
                    f"**Declined ({len(plan['declined'])}):** "
                    + ", ".join(m["name"] for m in plan["declined"])
                )
            if not plan["confirmed"] and not plan["pending"] and not plan["declined"]:
                lines.append("**No team assigned yet**")
            lines.append("")

        report = "\n".join(lines)
        summary = summarize(report, "upcoming services")
        if summary:
            report = f"*{summary}*\n\n{report}"
        return report

    @mcp.tool
    def search_prophecies(query: str, semantic: bool = False) -> str:
        """Search prophecies by keyword or semantic similarity.

        Args:
            query: Search text (keyword match or natural language for semantic).
            semantic: Use AI semantic search instead of keyword matching (default False).
        """
        if semantic:
            query_embedding = embed(query)
            if not query_embedding:
                return "Embedding service unavailable. Try keyword search instead."
            results = search_prophecies_semantic(db, query_embedding, top_k=10)
        else:
            results = search_prophecies_keyword(db, query)

        if not results:
            return f"No prophecies found matching '{query}'."

        lines = [f"## Prophecies — \"{query}\"", ""]
        for i, s in enumerate(results, 1):
            sim = f" ({round(s['similarity'] * 100)}% match)" if s.get("similarity") else ""
            lines.append(f"### {i}. {s['title']}{sim}")
            lines.append(f"*By {s['author_name']}* — {(s.get('submitted_at') or '?')[:10]}")
            if s.get("tags"):
                lines.append(f"Tags: {', '.join(s['tags'])}")
            preview = s["content"][:300]
            if len(s["content"]) > 300:
                preview += "..."
            lines.append(f"\n{preview}\n")

        return "\n".join(lines)

    @mcp.tool
    def get_prophecy_detail(prophecy_id: str) -> str:
        """Get full details of a specific prophecy by its ID.

        Args:
            prophecy_id: The prophecy's MongoDB ObjectId.
        """
        prophecy = get_prophecy(db, prophecy_id)
        if not prophecy:
            return f"No prophecy found with ID '{prophecy_id}'."

        lines = [f"## {prophecy['title']}"]
        lines.append(f"**Author:** {prophecy['author_name']} ({prophecy['author_type']})")
        if prophecy.get("submitted_at"):
            lines.append(f"**Submitted:** {prophecy['submitted_at'][:10]}")
        if prophecy.get("tags"):
            lines.append(f"**Tags:** {', '.join(prophecy['tags'])}")
        lines.append(f"**Status:** {prophecy['status']}")
        lines.append(f"\n{prophecy['content']}")

        return "\n".join(lines)
