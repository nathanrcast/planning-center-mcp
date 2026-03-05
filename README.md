# Planning Center MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server for [Planning Center Online Services](https://www.planningcenteronline.com/services). Gives AI agents (Claude, etc.) direct access to your worship plans, song library, teams, and volunteer data.

## Tools

### Services & Plans
| Tool | Description |
|------|-------------|
| `get_service_types` | List all service types |
| `get_plans` | Get plans for a service type (most recent first) |
| `get_plan_items` | Get songs, headers, and media in a plan |
| `get_plan_team_members` | Get volunteers assigned to a plan |

### Songs & Arrangements
| Tool | Description |
|------|-------------|
| `get_songs` | Paginated song library listing |
| `get_song` | Get a single song by ID |
| `find_song_by_title` | Search songs by title |
| `get_song_schedules` | Schedule history for a song |
| `get_all_arrangements_for_song` | List arrangements |
| `get_arrangement_for_song` | Get a specific arrangement |
| `get_keys_for_arrangement` | Available keys for an arrangement |
| `get_arrangement_attachments` | List file attachments (PDFs, audio, etc.) |
| `create_song` | Create a new song |

### Tags
| Tool | Description |
|------|-------------|
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
| `sync_pco_data` | Refresh the local MongoDB cache from PCO |
| `song_usage_report` | Ranked song usage over N months |
| `volunteer_activity_report` | Volunteer service frequency |
| `service_plan_report` | Recent plans with setlists and teams |
| `song_detail_report` | Full song details with schedule history |
| `upcoming_services_report` | Upcoming plans with team gaps |

### Prophecy Archive
| Tool | Description |
|------|-------------|
| `search_prophecies` | Keyword or semantic search across prophecies |
| `get_prophecy_detail` | Full text of a specific prophecy |

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

- **Direct tools** (`services.py`): Hit the PCO API live. No cache needed.
- **Report tools** (`reports.py`): Query a local MongoDB cache for aggregated data. Run `sync_pco_data` to refresh.
- **AI summaries** (`llm.py`): Optional. If an Ollama instance is available, reports include short AI-generated insights.

## Optional: AI Features

If you have [Ollama](https://ollama.ai) running, set `OLLAMA_URL` in `.env` to enable:
- AI-generated report summaries
- Semantic similarity search for prophecies

Models used: `nomic-embed-text` (embeddings), `llama3.2:3b` (summaries).
