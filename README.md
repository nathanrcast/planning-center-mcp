# Planning Center MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server for [Planning Center Online Services](https://www.planningcenteronline.com/services). Gives AI agents (Claude, etc.) direct access to your worship plans, song library, teams, and volunteer data.

Includes a built-in AI agent (`ask_question`) that accepts natural language questions and calls tools automatically using a local [Ollama](https://ollama.ai) model.

## Tools

### AI Agent
| Tool | Description |
|------|-------------|
| `ask_question` | Ask a natural language question about your PCO data. Uses a local Ollama model to call the appropriate tools and return a human-readable answer. |

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

**Sync**
| Tool | Description |
|------|-------------|
| `sync_pco_data` | Sync PCO data (incremental by default, `full=True` for complete re-sync) |
| `get_sync_status` | Check when the last sync occurred |
| `get_team_names` | All team names from synced data |

**Song Library**
| Tool | Description |
|------|-------------|
| `song_usage_report` | Ranked song play counts with optional date range and service type filters |
| `song_detail_report` | Full song details: arrangements, key-per-schedule history |
| `song_key_usage_report` | Keys ranked by frequency across all songs in a time period |
| `songs_by_key_report` | All songs ever played in a specific key (e.g. `G`, `Bb`), ranked by count |
| `songs_not_played_report` | Songs not played in the last N months — sorted by most recently used before the cutoff |
| `songs_played_together_report` | Songs most frequently paired with a given song in the same service |
| `song_retirement_report` | Songs that were played frequently in an older window but have since dropped off |
| `service_bpm_flow_report` | Tempo (BPM) and key progression across recent services, in song order |

**Service Plans**
| Tool | Description |
|------|-------------|
| `service_plan_report` | Recent plans with setlists (including key per song) and team rosters |
| `upcoming_services_report` | Upcoming plans with confirmed / pending / declined team members |
| `service_position_report` | Songs most commonly used in a given service position (`intro`, `outro`, `middle`) |

**Volunteers & People**
| Tool | Description |
|------|-------------|
| `volunteer_activity_report` | Volunteer frequency with optional team and date filters |
| `volunteer_decline_report` | Volunteers with the most declined requests, including decline rate |
| `person_song_keys_report` | Keys used in plans where a person served, optionally filtered by role |
| `person_song_preferences_report` | Songs played when a person served, optionally filtered by role |

---

## AI Agent: `ask_question`

The `ask_question` tool runs a multi-step tool-calling loop using a local Ollama model. It selects and chains the appropriate tools automatically based on your question, then returns a concise, human-readable answer.

### How It Works

1. Your question is sent to the Ollama model along with the schemas for 30 curated read-only tools
2. The model decides which tools to call and with what parameters
3. Tool results are fed back to the model
4. Steps 2–3 repeat (up to 10 iterations) until the model produces a final answer

### Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama instance URL |
| `AGENT_MODEL` | `mistral-small3.1` | Model to use for tool calling |

Any model with tool-calling support works. Larger models (24B+) are significantly more reliable at multi-step reasoning. Tested with `mistral-small3.1`.

### Example Questions

**Song Library**
```
What are our top 10 most played songs over the last 6 months?
When did we last play "How Great Is Our God"?
What key do we usually play "Blessed Be Your Name" in?
What songs have we not played in the last 3 months?
What songs have we quietly dropped from rotation this year?
```

**Keys & Setlist Planning**
```
What are the most popular keys we use?
What songs can we do in G?
What songs pair well with "Cornerstone"?
What do we usually open with?
What's our typical tempo arc through a service?
```

**Service Plans**
```
What songs are in this Sunday's service?
Show me the last 3 Sunday morning setlists with keys.
Which upcoming services have open volunteer spots?
What did we play on Easter?
```

**Volunteers & Teams**
```
Who are our most active volunteers over the last 3 months?
Who has been declining a lot of service requests lately?
Who is on the worship team this Sunday?
Which team positions are unfilled for next week?
```

**Person-Specific**
```
What keys does [name] play in when on guitar?
What songs does [name] tend to pick when leading worship?
What teams does [name] serve on?
```

**General**
```
When was the data last synced from Planning Center?
What service types do we have?
```

### Prompting Tips

- **Be specific with time ranges**: "last 3 months" or "since January" works better than "recently"
- **Name songs directly**: Use the song title as it appears in PCO for best results
- **Ask one thing at a time**: Multi-part questions ("top songs AND who played last week") can confuse the model — ask them separately
- **For volunteers, specify the team**: "Who is on the band this Sunday?" is clearer than "who is volunteering?"
- **Synced data vs live data**: Reports (song usage, volunteer activity, upcoming services) query the local MongoDB cache — run a sync first if your data may be stale. Direct lookups (`get_song`, `get_plans`) hit PCO live.
- **The agent won't modify data**: It only has access to read-only tools. Write operations (creating songs, assigning tags) must be called directly.

---

## Setup

### 1. Get PCO API Credentials

Create a Personal Access Token at the [PCO Developer Portal](https://api.planningcenteronline.com/oauth/applications).

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your PCO credentials, MongoDB password, and Ollama URL
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

---

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

---

## Architecture

```
PCO API ← pypco ─┬─ services.py   (direct API tools)
                 └─ sync.py ──── MongoDB ─┬─ queries.py ─ reports.py (cached reports)
                                          └─ llm.py (embeddings, optional AI summaries)

agent.py  ─ Ollama (tool-calling loop) ─ dispatches to any registered tool
```

- **Direct tools** (`services.py`): Hit the PCO API live. No cache needed.
- **Report tools** (`reports.py`): Query local MongoDB for aggregated data. Run `sync_pco_data` to refresh.
- **Sync** (`sync.py`): Incremental by default — only fetches records updated since the last sync.
- **Agent** (`agent.py`): Accepts a natural language question, builds an Ollama tool-calling loop over 30 curated read-only tools, and returns a plain-text answer.
- **AI features** (`llm.py`): Optional. Enables AI-generated summaries via Ollama.

---

## Development

```bash
pip install -e ".[dev]"
pytest
```
