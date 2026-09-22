from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from planning_center_mcp.queries import (
    song_usage,
    volunteer_activity,
    song_detail,
    upcoming_services,
    team_names_list,
    service_types_list,
    search_lyrics,
    songs_by_tags,
    songs_missing_lyrics,
    sync_status,
)


def _mock_db():
    return MagicMock()


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


class TestSearchLyrics:
    def _songs(self):
        return [
            {"_id": "1", "title": "Joyful Song", "tags": ["Praise Up Beat"],
             "arrangements": [{"lyrics": "There is joy in this house\nJoyful and glad"}],
             "raw_attributes": {"themes": "Praise"}},
            {"_id": "2", "title": "Rejoice", "tags": [],
             "arrangements": [{"lyrics": "Let the earth rejoicing sing"}],
             "raw_attributes": {"themes": None}},
        ]

    def test_searches_propresenter_lyrics_too(self):
        db = _mock_db()
        db.songs.find.return_value = [{
            "_id": "4", "title": "Resucito", "tags": [],
            "arrangements": [],
            "pro_lyrics": {"text": "Alegria, hermanos"},
            "raw_attributes": {},
        }]
        result = search_lyrics(db, ["alegr"])[0]
        assert result["matched_in"] == ["propresenter"]
        assert result["matching_lines"] == ["Alegria, hermanos"]

    def test_theme_only_match_is_labelled(self):
        db = _mock_db()
        db.songs.find.return_value = [{
            "_id": "5", "title": "Holy Is The Lord", "tags": [],
            "arrangements": [{"lyrics": "We stand and lift up our hands"}],
            "raw_attributes": {"themes": "Joy, Worship"},
        }]
        assert search_lyrics(db, ["joy"])[0]["matched_in"] == ["themes"]

    def test_matches_word_prefixes_and_ranks_by_count(self):
        db = _mock_db()
        db.songs.find.return_value = self._songs()
        results = search_lyrics(db, ["joy", "rejoic"])
        assert [r["title"] for r in results] == ["Joyful Song", "Rejoice"]
        assert results[0]["match_count"] == 2
        assert results[1]["matching_lines"] == ["Let the earth rejoicing sing"]

    def test_no_terms_returns_empty_without_querying(self):
        db = _mock_db()
        assert search_lyrics(db, []) == []
        db.songs.find.assert_not_called()

    def test_excludes_tags_and_hidden_songs(self):
        db = _mock_db()
        db.songs.find.return_value = []
        search_lyrics(db, ["joy"], exclude_tags=["Seasonal"])
        query = db.songs.find.call_args[0][0]
        assert {"pro_lyrics.text": {"$regex": query["$or"][1]["pro_lyrics.text"]["$regex"]}} in query["$or"]
        assert query["tags"] == {"$nin": ["Seasonal"]}
        assert query["raw_attributes.hidden"] == {"$ne": True}

    def test_include_hidden_drops_the_hidden_filter(self):
        db = _mock_db()
        db.songs.find.return_value = []
        search_lyrics(db, ["joy"], include_hidden=True)
        assert "raw_attributes.hidden" not in db.songs.find.call_args[0][0]

    def test_dedupes_repeated_lines(self):
        db = _mock_db()
        db.songs.find.return_value = [{
            "_id": "3", "title": "Repeat", "tags": [],
            "arrangements": [{"lyrics": "joy joy\njoy joy"}],
            "raw_attributes": {},
        }]
        result = search_lyrics(db, ["joy"])[0]
        assert result["match_count"] == 4
        assert result["matching_lines"] == ["joy joy"]


class TestSongsMissingLyrics:
    def test_sorts_by_title(self):
        db = _mock_db()
        db.songs.find.return_value = [
            {"_id": "2", "title": "Zion", "tags": []},
            {"_id": "1", "title": "Alleluia", "tags": ["Hymn"]},
        ]
        assert [s["title"] for s in songs_missing_lyrics(db)] == ["Alleluia", "Zion"]


class TestSongsByTags:
    def test_match_all_uses_all_operator(self):
        db = _mock_db()
        db.songs.find.return_value = []
        songs_by_tags(db, ["Praise Up Beat", "Joy"])
        assert db.songs.find.call_args[0][0] == {"tags": {"$all": ["Praise Up Beat", "Joy"]}}

    def test_match_any_uses_in_operator(self):
        db = _mock_db()
        db.songs.find.return_value = []
        songs_by_tags(db, ["Joy"], match_all=False)
        assert db.songs.find.call_args[0][0] == {"tags": {"$in": ["Joy"]}}

    def test_no_tags_returns_empty_without_querying(self):
        db = _mock_db()
        assert songs_by_tags(db, []) == []
        db.songs.find.assert_not_called()

    def test_sorts_by_title(self):
        db = _mock_db()
        db.songs.find.return_value = [
            {"_id": "2", "title": "Zion", "tags": ["Joy"]},
            {"_id": "1", "title": "alleluia", "tags": ["Joy"]},
        ]
        assert [s["title"] for s in songs_by_tags(db, ["Joy"])] == ["alleluia", "Zion"]
