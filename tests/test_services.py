from unittest.mock import MagicMock

from planning_center_mcp.services import slim_response, _pco_error_handler


class TestSlimResponse:
    def test_flattens_attributes(self):
        data = {
            "id": "1",
            "type": "Song",
            "attributes": {"title": "Amazing Grace"},
            "links": {"self": "http://..."},
            "relationships": {"tags": {}},
            "meta": {"can_edit": True},
        }
        result = slim_response(data)
        assert result == {"id": "1", "title": "Amazing Grace"}
        assert "type" not in result
        assert "links" not in result
        assert "attributes" not in result

    def test_strips_attribute_keys(self):
        data = {
            "id": "1",
            "attributes": {
                "title": "Test",
                "created_at": "2024-01-01",
                "updated_at": "2024-01-02",
                "permissions": "admin",
                "html_details": "<p>hi</p>",
                "notes_count": 5,
                "attachments_count": 2,
                "plan_notes_count": 1,
            },
        }
        result = slim_response(data)
        assert result == {"id": "1", "title": "Test"}

    def test_handles_list(self):
        data = [
            {"id": "1", "type": "Song", "attributes": {"title": "A"}, "links": {}},
            {"id": "2", "type": "Song", "attributes": {"title": "B"}, "meta": {}},
        ]
        result = slim_response(data)
        assert len(result) == 2
        assert result[0] == {"id": "1", "title": "A"}
        assert result[1] == {"id": "2", "title": "B"}

    def test_handles_primitives(self):
        assert slim_response("hello") == "hello"
        assert slim_response(42) == 42
        assert slim_response(None) is None

    def test_preserves_nested_non_attribute_dicts(self):
        data = {"id": "1", "custom": {"key": "value"}}
        result = slim_response(data)
        assert result["custom"] == {"key": "value"}

    def test_multiple_attributes_flattened(self):
        data = {
            "id": "1",
            "attributes": {"title": "Song", "author": "Bach", "bpm": 120},
        }
        result = slim_response(data)
        assert result == {"id": "1", "title": "Song", "author": "Bach", "bpm": 120}


class TestPcoErrorHandler:
    def _make_error(self, status_code):
        err = Exception("test")
        resp = MagicMock()
        resp.status_code = status_code
        err.response = resp
        return err

    def test_returns_result_on_success(self):
        @_pco_error_handler
        def ok():
            return {"data": "hello"}
        assert ok() == {"data": "hello"}

    def test_handles_401(self):
        @_pco_error_handler
        def fail():
            raise self._make_error(401)
        result = fail()
        assert "error" in result
        assert "Authentication" in result["error"]

    def test_handles_403(self):
        @_pco_error_handler
        def fail():
            raise self._make_error(403)
        result = fail()
        assert "Permission denied" in result["error"]

    def test_handles_404(self):
        @_pco_error_handler
        def fail():
            raise self._make_error(404)
        result = fail()
        assert "not found" in result["error"]

    def test_handles_429(self):
        @_pco_error_handler
        def fail():
            raise self._make_error(429)
        result = fail()
        assert "Rate limited" in result["error"]

    def test_handles_generic_error(self):
        @_pco_error_handler
        def fail():
            raise ValueError("something broke")
        result = fail()
        assert "error" in result
        assert "something broke" in result["error"]
