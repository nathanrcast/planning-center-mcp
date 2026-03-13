from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from planning_center_mcp.queries import (
    song_usage,
    volunteer_activity,
    song_detail,
    upcoming_services,
    team_names_list,
    service_types_list,
    sync_status,
    _cosine_similarity,
)


def _mock_db():
    return MagicMock()


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1, 0], [0, 1]) == 0.0

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 1]) == 0.0

    def test_similar_vectors(self):
        sim = _cosine_similarity([1, 1], [1, 0])
        assert 0.5 < sim < 1.0


class TestSongUsage:
    def test_returns_formatted_results(self):
        db = _mock_db()
        db.plans.aggregate.return_value = [
            {"title": "Song A", "count": 5, "last_played": "2024-06-15T00:00:00"},
            {"title": "Song B", "count": 2, "last_played": None},
        ]
        results = song_usage(db, months=3)
        assert len(results) == 2
        assert results[0]["title"] == "Song A"
        assert results[0]["count"] == 5
        assert results[0]["last_played"] == "2024-06-15"
        assert results[1]["last_played"] is None

    def test_uses_custom_date_range(self):
        db = _mock_db()
        db.plans.aggregate.return_value = []
        song_usage(db, months=3, start_date="2024-01-01", end_date="2024-06-30")
        pipeline = db.plans.aggregate.call_args[0][0]
        match_filter = pipeline[0]["$match"]
        assert match_filter["sort_date"]["$gte"] == "2024-01-01"
        assert match_filter["sort_date"]["$lte"] == "2024-06-30"

    def test_filters_by_service_type(self):
        db = _mock_db()
        db.plans.aggregate.return_value = []
        song_usage(db, months=3, service_type_ids=["123", "456"])
        pipeline = db.plans.aggregate.call_args[0][0]
        match_filter = pipeline[0]["$match"]
        assert match_filter["service_type_id"] == {"$in": ["123", "456"]}

    def test_empty_results(self):
        db = _mock_db()
        db.plans.aggregate.return_value = []
        assert song_usage(db, months=1) == []


class TestVolunteerActivity:
    def test_returns_formatted_results(self):
        db = _mock_db()
        db.plans.aggregate.return_value = [
            {"_id": "Alice", "count": 10, "teams": ["Band", "Vocals"]},
        ]
        results = volunteer_activity(db, months=3)
        assert len(results) == 1
        assert results[0]["name"] == "Alice"
        assert results[0]["count"] == 10
        assert "Band" in results[0]["teams"]

    def test_filters_by_team_names(self):
        db = _mock_db()
        db.plans.aggregate.return_value = []
        volunteer_activity(db, months=3, team_names=["Band"])
        pipeline = db.plans.aggregate.call_args[0][0]
        team_match = pipeline[2]["$match"]
        assert team_match["team_members.team_name"] == {"$in": ["Band"]}


class TestSongDetail:
    def test_returns_none_when_not_found(self):
        db = _mock_db()
        db.songs.find_one.return_value = None
        assert song_detail(db, "Nonexistent") is None

    def test_returns_song_with_schedules(self):
        db = _mock_db()
        db.songs.find_one.return_value = {
            "_id": "s1",
            "title": "Test Song",
            "author": "Author",
            "ccli_number": "12345",
            "arrangements": [{"name": "Default", "bpm": 120, "meter": "4/4"}],
        }
        db.plans.aggregate.return_value = [
            {"date": "2024-06-01T00:00:00", "service_type_name": "Sunday"},
        ]
        result = song_detail(db, "Test Song")
        assert result["title"] == "Test Song"
        assert result["author"] == "Author"
        assert len(result["arrangements"]) == 1
        assert result["schedules"][0]["date"] == "2024-06-01"


class TestUpcomingServices:
    def test_categorizes_team_members(self):
        db = _mock_db()
        db.plans.find.return_value = [
            {
                "dates": "June 1",
                "sort_date": "2099-06-01T00:00:00",
                "service_type_name": "Sunday",
                "team_members": [
                    {"name": "Alice", "status": "C", "position_name": "Keys"},
                    {"name": "Bob", "status": "D", "position_name": "Guitar"},
                    {"name": "Carol", "status": "Unconfirmed", "position_name": "Vocals"},
                ],
            }
        ]
        results = upcoming_services(db, weeks=4)
        assert len(results) == 1
        plan = results[0]
        assert len(plan["confirmed"]) == 1
        assert plan["confirmed"][0]["name"] == "Alice"
        assert len(plan["declined"]) == 1
        assert plan["declined"][0]["name"] == "Bob"
        assert len(plan["pending"]) == 1
        assert plan["pending"][0]["name"] == "Carol"


class TestHelperQueries:
    def test_team_names_list(self):
        db = _mock_db()
        db.plans.distinct.return_value = ["Band", None, "Vocals", ""]
        result = team_names_list(db)
        assert result == ["Band", "Vocals"]

    def test_service_types_list(self):
        db = _mock_db()
        db.service_types.find.return_value = [
            {"_id": "1", "name": "Sunday"},
            {"_id": "2", "name": "Wednesday"},
        ]
        result = service_types_list(db)
        assert result == [{"id": "1", "name": "Sunday"}, {"id": "2", "name": "Wednesday"}]

    def test_sync_status_with_data(self):
        db = _mock_db()
        db.sync_meta.find_one.return_value = {"_id": "last_sync", "timestamp": "2024-06-01T12:00:00"}
        assert sync_status(db) == {"last_sync": "2024-06-01T12:00:00"}

    def test_sync_status_no_data(self):
        db = _mock_db()
        db.sync_meta.find_one.return_value = None
        assert sync_status(db) == {"last_sync": None}
