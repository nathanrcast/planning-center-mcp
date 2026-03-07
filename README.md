# Planning Center MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server for [Planning Center Online Services](https://www.planningcenteronline.com/services). Gives AI agents (Claude, etc.) direct access to your worship plans, song library, teams, and volunteer data.

## Tools

### Services & Plans
| Tool | Description |
|------|-------------|
| `get_service_types` | List all service types |
| `get_plans` | Paginated plans for a service type (most recent first) |
| `get_plan_items` | Get songs, headers, and media in a plan |
| `get_plan_team_members` | Get volunteers assigned to a plan |
| `get_plan_details` | Get items and team members in one call |

### Songs & Arrangements
| Tool | Description |
|------|-------------|
| `get_songs` | Paginated song library listing |
| `get_song` | Get a song by ID or search by title |
| `get_song_schedules` | Schedule history for a song |
| `get_arrangements` | List arrangements, or get a specific one by ID |
| `get_keys_for_arrangement` | Available keys for an arrangement |
| `get_arrangement_attachments` | List file attachments (PDFs, audio, etc.) |
| `create_song` | Create a new song |

### Tags
| Tool | Description |
|------|-------------|
| `get_song_tags` | List all available song tags by group |
| `assign_tags_to_song` | Tag a song by tag name |
| `find_songs_by_tags` | Find songs matching tags (AND logic) |

### File Visibility (Attachment Types)
| Tool | Description |
|------|-------------|
| `get_attachment_types` | List org-level file classification types |
| `create_attachment_type` | Create custom types (Lead Sheet, Guitar Tab, etc.) |
| `get_team_positions` | Get teams, positions, and their attachment type mappings |
| `map_positions_to_attachment_types` | Assign which file types a position can see |
| `enable_attachment_types` | Toggle position-based file visibility on a service type |

### Reports (cached data)
| Tool | Description |
|------|-------------|
| `sync_pco_data` | Sync PCO data (incremental by default, `full=True` for complete re-sync) |
| `get_sync_status` | Check when the last sync occurred |
| `song_usage_report` | Ranked song usage with optional date range and service type filters |
| `volunteer_activity_report` | Volunteer frequency with optional team and date filters |
| `service_plan_report` | Recent plans with setlists and teams |
| `song_detail_report` | Full song details with schedule history |
| `upcoming_services_report` | Upcoming plans with team gaps |
| `get_team_names` | All team names from synced data |

### Prophecy Archive
| Tool | Description |
|------|-------------|
| `search_prophecies` | Keyword or semantic search across prophecies |
| `get_prophecy_detail` | Full text of a specific prophecy |
| `list_prophecies_report` | Browse prophecies with status/tag filters |
| `get_prophecy_tags` | List all prophecy tags |

## Setup

### 1. Get PCO API Credentials

Create a Personal Access Token at the [PCO Developer Portal](https://api.planningcenteronline.com/oauth/applications).

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your PCO credentials and MongoDB password
```

### 3. Run with Docker (recommended)

```bash
docker compose up -d
```

The MCP endpoint will be available at `http://localhost:8080/mcp`.

### 4. Run Locally (alternative)

```bash
pip install .
planning-center-mcp
```

Requires a running MongoDB instance (set `MONGO_URI` in `.env`).

## Connect to Claude

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "planning-center": {
      "type": "http",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

### Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "planning-center": {
      "type": "http",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## Architecture

```
PCO API ← pypco ← services.py (direct API tools)
                 ← sync.py → MongoDB ← queries.py ← reports.py (cached reports)
                                                    ← llm.py (optional AI summaries)
```

- **Direct tools** (`services.py`): Hit the PCO API live. No cache needed. All calls include error handling for auth, rate-limit, and not-found responses.
- **Report tools** (`reports.py`): Query a local MongoDB cache for aggregated data. Supports filtering by service type, date range, and team. Run `sync_pco_data` to refresh.
- **Sync** (`sync.py`): Incremental by default — only fetches records updated since the last sync. Use `sync_pco_data(full=True)` for a complete re-sync.
- **AI features** (`llm.py`): Optional. If an Ollama instance is available, enables semantic search for prophecies.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Optional: AI Features

If you have [Ollama](https://ollama.ai) running, set `OLLAMA_URL` in `.env` to enable:
- Semantic similarity search for prophecies

Model used: `nomic-embed-text` (embeddings).
