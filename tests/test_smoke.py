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
        with patch("src.server.PCO") as mock_pco, \
             patch("src.server.MongoClient") as mock_mongo:
            mock_db = MagicMock()
            mock_mongo.return_value.get_default_database.return_value = mock_db

            import importlib
            import src.server
            importlib.reload(src.server)
            yield src.server.mcp


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
            "volunteer_activity_report",
            "service_plan_report",
            "song_detail_report",
            "upcoming_services_report",
            "search_prophecies",
            "get_prophecy_detail",
            "get_sync_status",
            "get_team_names",
            "list_prophecies_report",
            "get_prophecy_tags",
        }
        missing = expected - tool_names
        assert not missing, f"Missing tools: {missing}"
