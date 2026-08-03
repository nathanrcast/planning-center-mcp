from unittest.mock import MagicMock

from planning_center_mcp.services import slim_response, _pco_error_handler, register_tools


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


def _register_and_get_tools(mock_pco):
    """Register tools with a mock PCO and return the locally-defined functions."""
    mock_mcp = MagicMock()
    captured = {}

    def fake_tool(func):
        captured[func.__name__] = func
        return func

    mock_mcp.tool = fake_tool
    register_tools(mock_mcp, mock_pco)
    return captured


class TestSearchPeople:
    def test_search_params_and_pagination(self):
        mock_pco = MagicMock()
        mock_pco.get.return_value = {
            "data": [
                {"id": "1", "type": "Person", "attributes": {"first_name": "John"}}
            ],
            "meta": {"total_count": 1},
        }
        tools = _register_and_get_tools(mock_pco)
        result = tools["search_people"](search="John", page=2, per_page=10)
        mock_pco.get.assert_called_once()
        call_kwargs = mock_pco.get.call_args
        assert call_kwargs[1]["per_page"] == 10
        assert call_kwargs[1]["offset"] == 10
        assert result["page"] == 2
        assert result["total"] == 1
        assert result["data"][0]["first_name"] == "John"

    def test_search_uses_correct_where_param(self):
        mock_pco = MagicMock()
        mock_pco.get.return_value = {"data": [], "meta": {"total_count": 0}}
        tools = _register_and_get_tools(mock_pco)
        tools["search_people"](search="test@example.com")
        call_kwargs = mock_pco.get.call_args
        assert call_kwargs[1]["where[search_name_or_email_or_phone_number]"] == "test@example.com"


class TestGetPerson:
    def test_merges_sub_resources(self):
        mock_pco = MagicMock()
        mock_pco.get.side_effect = [
            {"data": {"id": "1", "attributes": {"first_name": "Jane"}}},
            {"data": [{"id": "e1", "attributes": {"address": "jane@test.com"}}]},
            {"data": [{"id": "p1", "attributes": {"number": "555-1234"}}]},
            {"data": []},
        ]
        tools = _register_and_get_tools(mock_pco)
        result = tools["get_person"](person_id="1")
        assert result["first_name"] == "Jane"
        assert len(result["emails"]) == 1
        assert result["emails"][0]["address"] == "jane@test.com"
        assert len(result["phone_numbers"]) == 1
        assert result["addresses"] == []
        assert mock_pco.get.call_count == 4

    def test_empty_sub_resources(self):
        mock_pco = MagicMock()
        mock_pco.get.side_effect = [
            {"data": {"id": "2", "attributes": {"first_name": "Solo"}}},
            {"data": []},
            {"data": []},
            {"data": []},
        ]
        tools = _register_and_get_tools(mock_pco)
        result = tools["get_person"](person_id="2")
        assert result["first_name"] == "Solo"
        assert result["emails"] == []
        assert result["phone_numbers"] == []
        assert result["addresses"] == []


class TestUpdatePerson:
    def test_partial_update(self):
        mock_pco = MagicMock()
        mock_pco.template.return_value = {
            "data": {"type": "Person", "attributes": {"first_name": "Updated"}}
        }
        mock_pco.patch.return_value = {
            "data": {"id": "1", "attributes": {"first_name": "Updated", "last_name": "Doe"}}
        }
        tools = _register_and_get_tools(mock_pco)
        result = tools["update_person"](person_id="1", first_name="Updated")
        mock_pco.template.assert_called_once_with("Person", {"first_name": "Updated"})
        assert result["first_name"] == "Updated"

    def test_no_fields_error(self):
        mock_pco = MagicMock()
        tools = _register_and_get_tools(mock_pco)
        result = tools["update_person"](person_id="1")
        assert result == {"error": "No fields provided to update."}
        mock_pco.patch.assert_not_called()


class TestCreatePerson:
    def test_basic_creation(self):
        mock_pco = MagicMock()
        mock_pco.template.return_value = {
            "data": {"type": "Person", "attributes": {"first_name": "New", "last_name": "User"}}
        }
        mock_pco.post.return_value = {
            "data": {"id": "99", "attributes": {"first_name": "New", "last_name": "User"}}
        }
        tools = _register_and_get_tools(mock_pco)
        result = tools["create_person"](first_name="New", last_name="User")
        assert result["id"] == "99"
        assert mock_pco.post.call_count == 1

    def test_with_email_and_phone(self):
        mock_pco = MagicMock()
        mock_pco.template.side_effect = [
            {"data": {"type": "Person", "attributes": {}}},
            {"data": {"type": "Email", "attributes": {}}},
            {"data": {"type": "PhoneNumber", "attributes": {}}},
        ]
        mock_pco.post.side_effect = [
            {"data": {"id": "100", "attributes": {"first_name": "A", "last_name": "B"}}},
            {"data": {"id": "e1", "attributes": {"address": "a@b.com"}}},
            {"data": {"id": "p1", "attributes": {"number": "555-0000"}}},
        ]
        tools = _register_and_get_tools(mock_pco)
        result = tools["create_person"](
            first_name="A", last_name="B", email="a@b.com", phone="555-0000"
        )
        assert result["id"] == "100"
        assert result["email"]["address"] == "a@b.com"
        assert result["phone_number"]["number"] == "555-0000"
        assert mock_pco.post.call_count == 3


def _mock_pco_with_service_type(service_type_id="7"):
    """A mock whose plan lookup resolves the service type, as PCO does."""
    mock_pco = MagicMock()
    mock_pco.get.return_value = {
        "data": {"relationships": {"service_type": {"data": {"type": "ServiceType", "id": service_type_id}}}}
    }
    return mock_pco


class TestCreatePlanItem:
    def test_song_item_with_position(self):
        mock_pco = _mock_pco_with_service_type()
        mock_pco.template.return_value = {
            "data": {"type": "Item", "attributes": {"item_type": "song", "song_id": "42", "sequence": 5}}
        }
        mock_pco.post.return_value = {
            "data": {"id": "999", "attributes": {"item_type": "song", "title": "Our God", "sequence": 5}}
        }
        tools = _register_and_get_tools(mock_pco)
        result = tools["create_plan_item"](
            plan_id="1", item_type="song", song_id="42", sequence=5
        )
        mock_pco.template.assert_called_once_with(
            "Item", {"item_type": "song", "song_id": "42", "sequence": 5}
        )
        mock_pco.post.assert_called_once_with(
            "/services/v2/service_types/7/plans/1/items", mock_pco.template.return_value
        )
        assert result["id"] == "999"
        assert result["title"] == "Our God"

    def test_header_item_defaults(self):
        mock_pco = _mock_pco_with_service_type()
        mock_pco.template.return_value = {"data": {"type": "Item", "attributes": {"item_type": "header", "title": "Worship"}}}
        mock_pco.post.return_value = {"data": {"id": "1", "attributes": {"item_type": "header", "title": "Worship"}}}
        tools = _register_and_get_tools(mock_pco)
        tools["create_plan_item"](plan_id="1", item_type="header", title="Worship")
        mock_pco.template.assert_called_once_with("Item", {"item_type": "header", "title": "Worship"})

    def test_never_posts_to_redirecting_shortcut(self):
        """The /plans/{id}/items shortcut 302s and downgrades POST to GET."""
        mock_pco = _mock_pco_with_service_type()
        mock_pco.post.return_value = {"data": {"id": "1", "attributes": {}}}
        tools = _register_and_get_tools(mock_pco)
        tools["create_plan_item"](plan_id="1", item_type="header", title="Worship")
        url = mock_pco.post.call_args[0][0]
        assert url.startswith("/services/v2/service_types/")

    def test_service_type_lookup_is_cached_per_plan(self):
        mock_pco = _mock_pco_with_service_type()
        mock_pco.post.return_value = {"data": {"id": "1", "attributes": {}}}
        tools = _register_and_get_tools(mock_pco)
        tools["create_plan_item"](plan_id="1", item_type="header", title="A")
        tools["create_plan_item"](plan_id="1", item_type="header", title="B")
        assert mock_pco.get.call_count == 1


class TestUpdatePlanItem:
    def test_partial_update(self):
        mock_pco = _mock_pco_with_service_type()
        mock_pco.template.return_value = {"data": {"type": "Item", "attributes": {"sequence": 6}}}
        mock_pco.patch.return_value = {"data": {"id": "999", "attributes": {"sequence": 6}}}
        tools = _register_and_get_tools(mock_pco)
        result = tools["update_plan_item"](plan_id="1", item_id="999", sequence=6)
        mock_pco.template.assert_called_once_with("Item", {"sequence": 6})
        mock_pco.patch.assert_called_once_with(
            "/services/v2/service_types/7/plans/1/items/999", mock_pco.template.return_value
        )
        assert result["sequence"] == 6

    def test_no_fields_error(self):
        mock_pco = _mock_pco_with_service_type()
        tools = _register_and_get_tools(mock_pco)
        result = tools["update_plan_item"](plan_id="1", item_id="999")
        assert result == {"error": "No fields provided to update."}
        mock_pco.patch.assert_not_called()


class TestDeletePlanItem:
    def test_deletes_and_confirms(self):
        mock_pco = _mock_pco_with_service_type()
        tools = _register_and_get_tools(mock_pco)
        result = tools["delete_plan_item"](plan_id="1", item_id="999")
        mock_pco.delete.assert_called_once_with("/services/v2/service_types/7/plans/1/items/999")
        assert result == "Deleted item 999 from plan 1"


class TestGetPersonFieldData:
    def test_merges_field_definitions(self):
        mock_pco = MagicMock()
        mock_pco.get.return_value = {
            "data": [
                {
                    "id": "fd1",
                    "attributes": {"value": "Large"},
                    "relationships": {
                        "field_definition": {"data": {"type": "FieldDefinition", "id": "def1"}}
                    },
                }
            ],
            "included": [
                {
                    "id": "def1",
                    "type": "FieldDefinition",
                    "attributes": {"name": "T-Shirt Size", "data_type": "select"},
                }
            ],
        }
        tools = _register_and_get_tools(mock_pco)
        result = tools["get_person_field_data"](person_id="1")
        assert len(result) == 1
        assert result[0]["value"] == "Large"
        assert result[0]["field_name"] == "T-Shirt Size"
        assert result[0]["field_type"] == "select"

    def test_no_field_definitions(self):
        mock_pco = MagicMock()
        mock_pco.get.return_value = {
            "data": [
                {
                    "id": "fd2",
                    "attributes": {"value": "Yes"},
                    "relationships": {},
                }
            ],
            "included": [],
        }
        tools = _register_and_get_tools(mock_pco)
        result = tools["get_person_field_data"](person_id="2")
        assert len(result) == 1
        assert result[0]["value"] == "Yes"
        assert "field_name" not in result[0]
