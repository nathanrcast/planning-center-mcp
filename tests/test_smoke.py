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
            "get_songs",
            "get_song",
            "find_song_by_title",
            "create_song",
            "get_song_tags",
            "find_songs_by_tags",
            "sync_pco_data",
            "song_usage_report",
            "volunteer_activity_report",
            "get_sync_status",
            "get_team_names",
            "get_service_types_cached",
        }
        missing = expected - tool_names
        assert not missing, f"Missing tools: {missing}"
