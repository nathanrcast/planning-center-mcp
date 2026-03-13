import threading
from unittest.mock import MagicMock, patch

from planning_center_mcp.sync import SyncManager


def _make_sync_manager():
    db = MagicMock()
    db.sync_meta.find_one.return_value = None
    pco = MagicMock()
    pco.iterate.return_value = iter([])
    return SyncManager(db, pco)


class TestSyncLock:
    def test_rejects_concurrent_sync(self):
        mgr = _make_sync_manager()
        # Acquire the lock manually to simulate an in-progress sync
        mgr._lock.acquire()
        try:
            result = mgr.sync_all()
            assert "error" in result
            assert "already in progress" in result["error"]
        finally:
            mgr._lock.release()

    def test_allows_sync_after_previous_completes(self):
        mgr = _make_sync_manager()
        result1 = mgr.sync_all()
        assert "error" not in result1
        result2 = mgr.sync_all()
        assert "error" not in result2

    def test_full_sync_ignores_last_sync(self):
        mgr = _make_sync_manager()
        mgr.db.sync_meta.find_one.return_value = {"_id": "last_sync", "timestamp": "2024-01-01"}
        result = mgr.sync_all(full=True)
        assert result["mode"] == "full"

    def test_incremental_sync_uses_last_sync(self):
        mgr = _make_sync_manager()
        mgr.db.sync_meta.find_one.return_value = {"_id": "last_sync", "timestamp": "2024-01-01"}
        result = mgr.sync_all(full=False)
        assert result["mode"] == "incremental"

    def test_records_duration(self):
        mgr = _make_sync_manager()
        result = mgr.sync_all()
        assert "duration_seconds" in result
        assert isinstance(result["duration_seconds"], float)

    def test_captures_phase_errors(self):
        mgr = _make_sync_manager()
        mgr.pco.iterate.side_effect = RuntimeError("API down")
        result = mgr.sync_all()
        assert "errors" in result
        assert any("API down" in e for e in result["errors"])
