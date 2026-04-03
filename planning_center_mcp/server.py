import logging
import os
import sys
import threading

from dotenv import load_dotenv
from fastmcp import FastMCP
from pymongo import MongoClient, ASCENDING, TEXT
from pypco import PCO

from planning_center_mcp.agent import register_agent_tool
from planning_center_mcp.reports import register_report_tools
from planning_center_mcp.services import register_tools
from planning_center_mcp.sync import SyncManager

load_dotenv()
log = logging.getLogger(__name__)

pco_app_id = os.getenv("PCO_APPLICATION_ID")
pco_secret = os.getenv("PCO_SECRET_KEY")
if not pco_app_id or not pco_secret:
    sys.exit("ERROR: PCO_APPLICATION_ID and PCO_SECRET_KEY must be set in .env")

mcp = FastMCP("Planning Center")

pco = PCO(application_id=pco_app_id, secret=pco_secret)

mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/planning_center"))
db = mongo_client.get_default_database()

sync_mgr = SyncManager(db, pco)

register_tools(mcp, pco)
register_report_tools(mcp, db, sync_mgr)
register_agent_tool(mcp)


def _ensure_indexes():
    db.plans.create_index([("sort_date", ASCENDING)])
    db.plans.create_index([("service_type_id", ASCENDING)])
    db.plans.create_index([("service_type_name", ASCENDING)])
    db.songs.create_index([("title", ASCENDING)])
    db.stories.create_index([("status", ASCENDING)])
    db.stories.create_index([("title", TEXT), ("content", TEXT)])


def _startup_sync():
    try:
        _ensure_indexes()
        last = sync_mgr.get_last_sync()
        if last is None:
            log.info("No previous sync found — running initial sync...")
            stats = sync_mgr.sync_all()
            log.info("Initial sync complete: %s", stats)
        else:
            log.info("Last sync: %s — skipping startup sync (use sync_pco_data tool to refresh)", last)
    except Exception:
        log.exception("Startup sync failed")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    threading.Thread(target=_startup_sync, daemon=True).start()
    mcp.run(transport="http", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
