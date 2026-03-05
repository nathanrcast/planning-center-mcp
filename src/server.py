import os
import threading

from dotenv import load_dotenv
from fastmcp import FastMCP
from pymongo import MongoClient
from pypco import PCO

from src.reports import register_report_tools
from src.services import register_tools
from src.sync import SyncManager

load_dotenv()

mcp = FastMCP("Planning Center")

pco = PCO(
    application_id=os.getenv("PCO_APPLICATION_ID"),
    secret=os.getenv("PCO_SECRET_KEY"),
)

mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/planning_center"))
db = mongo_client.get_default_database()

register_tools(mcp, pco)
register_report_tools(mcp, db, pco)


def _startup_sync():
    try:
        sync_mgr = SyncManager(db, pco)
        last = sync_mgr.get_last_sync()
        if last is None:
            print("No previous sync found — running initial sync...")
            stats = sync_mgr.sync_all()
            print(f"Initial sync complete: {stats}")
        else:
            print(f"Last sync: {last} — skipping startup sync (use sync_pco_data tool to refresh)")
    except Exception as e:
        print(f"Startup sync failed: {e}")


def main():
    threading.Thread(target=_startup_sync, daemon=True).start()
    mcp.run(transport="http", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
