from pypco import PCO

STRIP_KEYS = {"links", "relationships", "included", "meta"}
STRIP_ATTR_KEYS = {
    "created_at", "updated_at", "permissions", "html_details",
    "notes_count", "attachments_count", "plan_notes_count",
}


def slim_response(data):
    if isinstance(data, list):
        return [slim_response(item) for item in data]
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in STRIP_KEYS:
                continue
            if k == "attributes" and isinstance(v, dict):
                result[k] = {ak: av for ak, av in v.items() if ak not in STRIP_ATTR_KEYS}
            else:
                result[k] = v
        return result
    return data


def register_tools(mcp: object, pco: PCO):
    """Register all PCO Services tools on the given FastMCP server."""

    @mcp.tool
    def get_service_types() -> list:
        """Get all service types from Planning Center Services."""
        response = pco.get("/services/v2/service_types")
        return slim_response(response["data"])

    @mcp.tool
    def get_plans(service_type_id: str) -> list:
        """Get plans for a given service type, ordered by most recently updated."""
        response = pco.get(
            f"/services/v2/service_types/{service_type_id}/plans",
            order="-updated_at",
        )
        return slim_response(response["data"])

    @mcp.tool
    def get_plan_items(plan_id: str) -> list:
        """Get all items (songs, headers, media) within a specific plan."""
        response = pco.get(f"/services/v2/plans/{plan_id}/items")
        return slim_response(response["data"])

    @mcp.tool
    def get_plan_team_members(plan_id: str) -> list:
        """Get team members assigned to a specific plan (volunteers, band, etc.)."""
        response = pco.get(f"/services/v2/plans/{plan_id}/team_members")
        return slim_response(response["data"])

    @mcp.tool
    def get_songs(page: int = 1, per_page: int = 100) -> dict:
        """Get songs from the library. Returns paginated results with total count.

        Args:
            page: Page number (1-based).
            per_page: Results per page (max 100).
        """
        offset = (page - 1) * per_page
        response = pco.get(
            "/services/v2/songs",
            where={"hidden": "false"},
            per_page=per_page,
            offset=offset,
        )
        return {
            "data": slim_response(response["data"]),
            "total": response.get("meta", {}).get("total_count"),
            "page": page,
            "per_page": per_page,
        }

    @mcp.tool
    def get_song(song_id: str) -> dict:
        """Get details for a specific song by ID."""
        response = pco.get(f"/services/v2/songs/{song_id}")
        return slim_response(response["data"])

    @mcp.tool
    def find_song_by_title(title: str) -> list:
        """Search for songs by title (case-insensitive partial match)."""
        response = pco.get("/services/v2/songs", where={"title": title})
        return slim_response(response["data"])

    @mcp.tool
    def get_song_schedules(song_id: str) -> list:
        """Get schedule history for a song — shows every service where it was used.

        Useful for answering questions like 'when did we last play this song?'
        or 'how often do we use this song?'.
        """
        response = pco.get(
            f"/services/v2/songs/{song_id}/song_schedules",
            order="-plan_sort_date",
        )
        return slim_response(response["data"])

    @mcp.tool
    def get_all_arrangements_for_song(song_id: str) -> list:
        """Get all arrangements for a specific song."""
        response = pco.get(f"/services/v2/songs/{song_id}/arrangements")
        return slim_response(response["data"])

    @mcp.tool
    def get_arrangement_for_song(song_id: str, arrangement_id: str) -> dict:
        """Get a specific arrangement for a song."""
        response = pco.get(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}"
        )
        return slim_response(response["data"])

    @mcp.tool
    def get_keys_for_arrangement(song_id: str, arrangement_id: str) -> list:
        """Get available keys for a specific arrangement of a song."""
        response = pco.get(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/keys"
        )
        return slim_response(response["data"])

    @mcp.tool
    def create_song(title: str, ccli: str = None) -> dict:
        """Create a new song in the library.

        Args:
            title: Song title.
            ccli: Optional CCLI number.
        """
        attrs = {"title": title}
        if ccli:
            attrs["ccli_number"] = ccli
        payload = pco.template("Song", attrs)
        response = pco.post("/services/v2/songs", payload)
        return slim_response(response["data"])

    @mcp.tool
    def assign_tags_to_song(song_id: str, tag_names: list[str]) -> str:
        """Assign tags to a song by tag name.

        Args:
            song_id: The song ID.
            tag_names: List of tag names to assign.
        """
        tag_groups_response = pco.get(
            "/services/v2/tag_groups", include="tags", filter="song"
        )
        all_tags = tag_groups_response.get("included", [])
        tag_ids = [
            t["id"] for t in all_tags if t["attributes"]["name"] in tag_names
        ]
        if not tag_ids:
            return f"No matching tags found for: {tag_names}"
        body = {
            "data": {
                "type": "TagAssignment",
                "relationships": {
                    "tags": {"data": [{"type": "Tag", "id": tid} for tid in tag_ids]}
                },
            }
        }
        pco.post(f"/services/v2/songs/{song_id}/assign_tags", body)
        return f"Assigned {len(tag_ids)} tag(s) to song {song_id}"

    @mcp.tool
    def get_arrangement_attachments(song_id: str, arrangement_id: str) -> list:
        """Get file attachments for a specific arrangement of a song.

        Returns PDFs, chord charts, audio files, etc. attached to the arrangement.
        Includes relationship data for inspecting file visibility settings.

        Args:
            song_id: The song ID.
            arrangement_id: The arrangement ID.
        """
        response = pco.get(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments"
        )
        items = response.get("data", [])
        result = []
        for item in items:
            entry = {
                "type": item.get("type"),
                "id": item.get("id"),
                "attributes": {
                    k: v for k, v in item.get("attributes", {}).items()
                    if k not in STRIP_ATTR_KEYS
                },
            }
            if "relationships" in item:
                entry["relationships"] = item["relationships"]
            result.append(entry)
        return result

    @mcp.tool
    def get_team_positions(service_type_id: str) -> list:
        """Get teams and their positions for a service type.

        Includes current attachment_type mappings for each position (used for
        file visibility). Useful for mapping volunteer roles (Guitarist, Keys,
        Vocalist, etc.) to file visibility on arrangement attachments.

        Args:
            service_type_id: The service type ID.
        """
        teams = []
        for team_resp in pco.iterate(
            f"/services/v2/service_types/{service_type_id}/teams",
            include="team_positions",
        ):
            team_data = team_resp["data"]
            included = team_resp.get("included", [])
            positions = []
            for p in included:
                if p["type"] != "TeamPosition":
                    continue
                at_data = (p.get("relationships", {})
                           .get("attachment_types", {})
                           .get("data", []))
                positions.append({
                    "id": p["id"],
                    "name": p["attributes"]["name"],
                    "attachment_type_ids": [a["id"] for a in at_data],
                })
            teams.append({
                "id": team_data["id"],
                "name": team_data["attributes"]["name"],
                "positions": positions,
            })
        return teams

    @mcp.tool
    def get_attachment_types() -> dict:
        """Get all attachment type groups and their types.

        Returns the org-level classification system for files (e.g., Chord Chart,
        Lyrics, Lead Sheet). These types control which team positions see which files
        when attachment_types_enabled is true on a service type.
        """
        groups_resp = pco.get("/services/v2/attachment_type_groups")
        groups = []
        for g in groups_resp["data"]:
            types_resp = pco.get(
                f"/services/v2/attachment_type_groups/{g['id']}/attachment_types"
            )
            groups.append({
                "id": g["id"],
                "name": g["attributes"]["name"],
                "readonly": g["attributes"].get("readonly", False),
                "types": [
                    {"id": t["id"], "name": t["attributes"]["name"],
                     "aliases": t["attributes"].get("aliases", []),
                     "built_in": t["attributes"].get("built_in", False)}
                    for t in types_resp["data"]
                ],
            })
        return {"groups": groups}

    @mcp.tool
    def create_attachment_type(name: str, group_id: str = None, group_name: str = None) -> dict:
        """Create a custom attachment type for file classification.

        Creates a new attachment type (e.g., 'Lead Sheet', 'Guitar Tab'). If no
        group_id is given, creates a new group with group_name (or 'Custom').

        Args:
            name: The attachment type name.
            group_id: Existing attachment type group ID.
            group_name: Name for a new group (used if group_id is not provided).
        """
        if not group_id:
            grp = pco.post("/services/v2/attachment_type_groups", {
                "data": {"type": "AttachmentTypeGroup",
                         "attributes": {"name": group_name or "Custom"}}
            })
            group_id = grp["data"]["id"]
        payload = {
            "data": {
                "type": "AttachmentType",
                "attributes": {"name": name},
                "relationships": {
                    "attachment_type_group": {
                        "data": {"type": "AttachmentTypeGroup", "id": group_id}
                    }
                },
            }
        }
        response = pco.post("/services/v2/attachment_types", payload)
        return {
            "id": response["data"]["id"],
            "name": response["data"]["attributes"]["name"],
            "group_id": group_id,
        }

    @mcp.tool
    def map_positions_to_attachment_types(
        service_type_id: str,
        team_id: str,
        position_id: str,
        attachment_type_ids: list[str],
    ) -> dict:
        """Map attachment types to a team position for file visibility.

        When attachment_types_enabled is true on the service type, volunteers in
        this position will only see files matching the assigned attachment types.

        Args:
            service_type_id: The service type ID.
            team_id: The team ID.
            position_id: The team position ID.
            attachment_type_ids: List of attachment type IDs to assign.
        """
        payload = {
            "data": {
                "type": "TeamPosition",
                "id": position_id,
                "relationships": {
                    "attachment_types": {
                        "data": [
                            {"type": "AttachmentType", "id": tid}
                            for tid in attachment_type_ids
                        ]
                    }
                },
            }
        }
        response = pco.patch(
            f"/services/v2/service_types/{service_type_id}/teams/{team_id}/team_positions/{position_id}",
            payload,
        )
        mapped = response["data"]["relationships"]["attachment_types"]["data"]
        return {
            "position_id": position_id,
            "attachment_types": [m["id"] for m in mapped],
        }

    @mcp.tool
    def enable_attachment_types(service_type_id: str, enabled: bool = True) -> dict:
        """Enable or disable attachment type visibility on a service type.

        When enabled, volunteers only see files matching their position's
        assigned attachment types.

        Args:
            service_type_id: The service type ID.
            enabled: True to enable, False to disable.
        """
        payload = pco.template("ServiceType", {"attachment_types_enabled": enabled})
        response = pco.patch(
            f"/services/v2/service_types/{service_type_id}", payload
        )
        return {
            "service_type_id": service_type_id,
            "name": response["data"]["attributes"]["name"],
            "attachment_types_enabled": response["data"]["attributes"]["attachment_types_enabled"],
        }

    @mcp.tool
    def find_songs_by_tags(tag_names: list[str]) -> list:
        """Find songs that match ALL specified tags (AND logic).

        Args:
            tag_names: List of tag names — songs must have all of them.
        """
        tag_groups_response = pco.get(
            "/services/v2/tag_groups", include="tags", filter="song"
        )
        all_tags = tag_groups_response.get("included", [])
        tag_ids = [
            t["id"] for t in all_tags if t["attributes"]["name"] in tag_names
        ]
        if not tag_ids:
            return []
        params = {"where[song_tag_ids]": ",".join(tag_ids)}
        response = pco.get("/services/v2/songs", **params)
        return slim_response(response["data"])
