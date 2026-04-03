import asyncio
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mcp_app():
    """Import server module with mocked external dependencies."""
    with patch.dict("os.environ", {
        "PCO_APPLICATION_ID": "test_id",
        "PCO_SECRET_KEY": "test_secret",
        "MONGO_URI": "mongodb://localhost:27017/test_db",
    }):
        with patch("planning_center_mcp.server.PCO") as mock_pco, \
             patch("planning_center_mcp.server.MongoClient") as mock_mongo:
            mock_db = MagicMock()
            mock_mongo.return_value.get_default_database.return_value = mock_db

            import importlib
            import planning_center_mcp.server
            importlib.reload(planning_center_mcp.server)
            yield planning_center_mcp.server.mcp


def _list_tool_names(mcp_app):
    tools = asyncio.run(mcp_app.list_tools())
    return {t.name for t in tools}


class TestSmoke:
    def test_server_has_tools(self, mcp_app):
        tool_names = _list_tool_names(mcp_app)
        assert len(tool_names) > 0

    def test_expected_tools_registered(self, mcp_app):
        tool_names = _list_tool_names(mcp_app)
        expected = {
            "get_service_types",
            "get_plans",
            "get_plan_items",
            "get_plan_team_members",
            "get_plan_details",
            "get_songs",
            "get_song",
            "get_song_schedules",
            "get_arrangements",
            "get_keys_for_arrangement",
            "create_song",
            "assign_tags_to_song",
            "get_arrangement_attachments",
            "get_team_positions",
            "get_attachment_types",
            "create_attachment_type",
            "map_positions_to_attachment_types",
            "enable_attachment_types",
            "get_song_tags",
            "find_songs_by_tags",
            "sync_pco_data",
            "song_usage_report",
            "song_key_usage_report",
            "person_song_keys_report",
            "person_song_preferences_report",
            "songs_not_played_report",
            "songs_by_key_report",
            "songs_played_together_report",
            "service_position_report",
            "service_bpm_flow_report",
            "song_retirement_report",
            "volunteer_decline_report",
            "volunteer_activity_report",
            "service_plan_report",
            "song_detail_report",
            "upcoming_services_report",
            "get_sync_status",
            "get_team_names",
            "search_people",
            "get_person",
            "update_person",
            "create_person",
            "get_person_field_data",
        }
        missing = expected - tool_names
        assert not missing, f"Missing tools: {missing}"
