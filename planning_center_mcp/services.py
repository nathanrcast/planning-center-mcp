import functools
import logging

from pypco import PCO

log = logging.getLogger(__name__)

STRIP_KEYS = {"links", "relationships", "included", "meta", "type"}
STRIP_ATTR_KEYS = {
    "created_at", "updated_at", "permissions", "html_details",
    "notes_count", "attachments_count", "plan_notes_count",
}


def slim_response(data):
    """Flatten PCO JSON: merge attributes into top-level, drop type/links/meta."""
    if isinstance(data, list):
        return [slim_response(item) for item in data]
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in STRIP_KEYS:
                continue
            if k == "attributes" and isinstance(v, dict):
                for ak, av in v.items():
                    if ak not in STRIP_ATTR_KEYS:
                        result[ak] = av
            else:
                result[k] = v
        return result
    return data


def _pco_error_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            name = func.__name__
            log.exception("PCO API error in %s", name)
            status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
            if status == 401:
                return {"error": "Authentication failed. Check your PCO_APPLICATION_ID and PCO_SECRET_KEY."}
            if status == 403:
                return {"error": "Permission denied. Your API token may lack access to this resource."}
            if status == 404:
                return {"error": f"Resource not found. Check that the IDs passed to {name} are correct."}
            if status == 429:
                return {"error": "Rate limited by Planning Center. Wait a moment and try again."}
            return {"error": f"{name} failed: {e}"}
    return wrapper


def register_tools(mcp: object, pco: PCO):
    """Register all PCO Services tools on the given FastMCP server."""

    @mcp.tool
    @_pco_error_handler
    def get_service_types() -> list:
        """List all service types."""
        response = pco.get("/services/v2/service_types")
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def get_plans(service_type_id: str, page: int = 1, per_page: int = 25) -> dict:
        """Get plans for a service type (most recent first). Paginated."""
        offset = (page - 1) * per_page
        response = pco.get(
            f"/services/v2/service_types/{service_type_id}/plans",
            order="-updated_at",
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
    @_pco_error_handler
    def get_plan_items(plan_id: str) -> list:
        """Get songs, headers, and media in a plan."""
        response = pco.get(f"/services/v2/plans/{plan_id}/items")
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def get_plan_team_members(plan_id: str) -> list:
        """Get volunteers assigned to a plan."""
        response = pco.get(f"/services/v2/plans/{plan_id}/team_members")
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def get_plan_details(plan_id: str) -> dict:
        """Get a plan's items and team members in one call."""
        items_resp = pco.get(f"/services/v2/plans/{plan_id}/items")
        team_resp = pco.get(f"/services/v2/plans/{plan_id}/team_members")
        return {
            "items": slim_response(items_resp["data"]),
            "team_members": slim_response(team_resp["data"]),
        }

    @mcp.tool
    @_pco_error_handler
    def get_songs(page: int = 1, per_page: int = 100) -> dict:
        """Paginated song library listing."""
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
    @_pco_error_handler
    def get_song(song_id: str = None, title: str = None) -> list | dict:
        """Get a song by ID or search by title. Provide one or the other."""
        if song_id:
            response = pco.get(f"/services/v2/songs/{song_id}")
            return slim_response(response["data"])
        if title:
            response = pco.get("/services/v2/songs", where={"title": title})
            return slim_response(response["data"])
        return {"error": "Provide song_id or title."}

    @mcp.tool
    @_pco_error_handler
    def get_song_schedules(song_id: str) -> list:
        """Schedule history for a song — when and how often it was used."""
        response = pco.get(
            f"/services/v2/songs/{song_id}/song_schedules",
            order="-plan_sort_date",
        )
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def get_arrangements(song_id: str, arrangement_id: str = None) -> list | dict:
        """Get arrangements for a song. Pass arrangement_id for a specific one."""
        if arrangement_id:
            response = pco.get(
                f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}"
            )
            return slim_response(response["data"])
        response = pco.get(f"/services/v2/songs/{song_id}/arrangements")
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def get_keys_for_arrangement(song_id: str, arrangement_id: str) -> list:
        """Available keys for an arrangement."""
        response = pco.get(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/keys"
        )
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def create_song(title: str, ccli: str = None) -> dict:
        """Create a new song. Optional CCLI number."""
        attrs = {"title": title}
        if ccli:
            attrs["ccli_number"] = ccli
        payload = pco.template("Song", attrs)
        response = pco.post("/services/v2/songs", payload)
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def assign_tags_to_song(song_id: str, tag_names: list[str]) -> str:
        """Tag a song. Use get_song_tags to discover valid names."""
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
    @_pco_error_handler
    def get_arrangement_attachments(song_id: str, arrangement_id: str) -> list:
        """File attachments (PDFs, charts, audio) for an arrangement."""
        response = pco.get(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments"
        )
        items = response.get("data", [])
        result = []
        for item in items:
            entry = {"id": item.get("id")}
            for ak, av in item.get("attributes", {}).items():
                if ak not in STRIP_ATTR_KEYS:
                    entry[ak] = av
            if "relationships" in item:
                entry["relationships"] = item["relationships"]
            result.append(entry)
        return result

    @mcp.tool
    @_pco_error_handler
    def get_team_positions(service_type_id: str) -> list:
        """Teams, positions, and their attachment type mappings for a service type."""
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
    @_pco_error_handler
    def get_attachment_types() -> dict:
        """Org-level file classification types (Chord Chart, Lyrics, etc.)."""
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
    @_pco_error_handler
    def create_attachment_type(name: str, group_id: str = None, group_name: str = None) -> dict:
        """Create a file type (e.g. Lead Sheet). Creates a new group if no group_id given."""
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
    @_pco_error_handler
    def map_positions_to_attachment_types(
        service_type_id: str,
        team_id: str,
        position_id: str,
        attachment_type_ids: list[str],
    ) -> dict:
        """Set which file types a position can see."""
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
    @_pco_error_handler
    def enable_attachment_types(service_type_id: str, enabled: bool = True) -> dict:
        """Toggle position-based file visibility on a service type."""
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
    @_pco_error_handler
    def get_song_tags() -> list:
        """All song tags grouped by tag group. Use before assign_tags or find_songs_by_tags."""
        response = pco.get(
            "/services/v2/tag_groups", include="tags", filter="song"
        )
        groups = []
        included = response.get("included", [])
        for g in response.get("data", []):
            group_tag_ids = {
                t["id"]
                for t in (g.get("relationships", {}).get("tags", {}).get("data", []))
            }
            tags = [
                t["attributes"]["name"]
                for t in included
                if t["id"] in group_tag_ids
            ]
            groups.append({
                "group": g["attributes"]["name"],
                "tags": tags,
            })
        return groups

    @mcp.tool
    @_pco_error_handler
    def find_songs_by_tags(tag_names: list[str]) -> list:
        """Find songs matching ALL given tags (AND logic)."""
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

    # --- People API tools ---

    @mcp.tool
    @_pco_error_handler
    def search_people(
        search: str, page: int = 1, per_page: int = 25
    ) -> dict:
        """Search people by name, email, or phone number."""
        offset = (page - 1) * per_page
        response = pco.get(
            "/people/v2/people",
            **{"where[search_name_or_email_or_phone_number]": search},
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
    @_pco_error_handler
    def get_person(person_id: str) -> dict:
        """Get full person details including emails, phone numbers, and addresses."""
        person_resp = pco.get(f"/people/v2/people/{person_id}")
        emails_resp = pco.get(f"/people/v2/people/{person_id}/emails")
        phones_resp = pco.get(f"/people/v2/people/{person_id}/phone_numbers")
        addresses_resp = pco.get(f"/people/v2/people/{person_id}/addresses")
        result = slim_response(person_resp["data"])
        result["emails"] = slim_response(emails_resp["data"])
        result["phone_numbers"] = slim_response(phones_resp["data"])
        result["addresses"] = slim_response(addresses_resp["data"])
        return result

    @mcp.tool
    @_pco_error_handler
    def update_person(
        person_id: str,
        first_name: str = None,
        last_name: str = None,
        gender: str = None,
        birthdate: str = None,
        child: bool = None,
        membership: str = None,
        status: str = None,
    ) -> dict:
        """Update a person's attributes. Only provided fields are changed."""
        attrs = {}
        if first_name is not None:
            attrs["first_name"] = first_name
        if last_name is not None:
            attrs["last_name"] = last_name
        if gender is not None:
            attrs["gender"] = gender
        if birthdate is not None:
            attrs["birthdate"] = birthdate
        if child is not None:
            attrs["child"] = child
        if membership is not None:
            attrs["membership"] = membership
        if status is not None:
            attrs["status"] = status
        if not attrs:
            return {"error": "No fields provided to update."}
        payload = pco.template("Person", attrs)
        response = pco.patch(f"/people/v2/people/{person_id}", payload)
        return slim_response(response["data"])

    @mcp.tool
    @_pco_error_handler
    def create_person(
        first_name: str,
        last_name: str,
        email: str = None,
        phone: str = None,
    ) -> dict:
        """Create a new person. Optionally add an email and/or phone number."""
        payload = pco.template("Person", {
            "first_name": first_name,
            "last_name": last_name,
        })
        response = pco.post("/people/v2/people", payload)
        result = slim_response(response["data"])
        person_id = response["data"]["id"]
        if email:
            email_payload = pco.template("Email", {
                "address": email,
                "location": "Home",
                "primary": True,
            })
            email_resp = pco.post(
                f"/people/v2/people/{person_id}/emails", email_payload
            )
            result["email"] = slim_response(email_resp["data"])
        if phone:
            phone_payload = pco.template("PhoneNumber", {
                "number": phone,
                "location": "Mobile",
                "primary": True,
            })
            phone_resp = pco.post(
                f"/people/v2/people/{person_id}/phone_numbers", phone_payload
            )
            result["phone_number"] = slim_response(phone_resp["data"])
        return result

    @mcp.tool
    @_pco_error_handler
    def get_person_field_data(person_id: str) -> list:
        """Get custom field data for a person (e.g. spiritual gifts, t-shirt size)."""
        response = pco.get(
            f"/people/v2/people/{person_id}/field_data",
            include="field_definition",
        )
        included = {
            item["id"]: item["attributes"]
            for item in response.get("included", [])
        }
        results = []
        for item in response["data"]:
            entry = slim_response(item)
            fd_data = (
                item.get("relationships", {})
                .get("field_definition", {})
                .get("data", {})
            )
            fd_id = fd_data.get("id") if fd_data else None
            if fd_id and fd_id in included:
                entry["field_name"] = included[fd_id].get("name")
                entry["field_type"] = included[fd_id].get("data_type")
            results.append(entry)
        return results
