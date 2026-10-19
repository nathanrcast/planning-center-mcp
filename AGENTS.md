# planning-center-mcp — agent notes

MCP server + pip package for Planning Center Online (Services): PCO API tools, a MongoDB cache with report queries, and an Ollama-backed `ask_question` agent. Tool list and setup: `README.md`. **Public repo** — lab details go in the gitignored `CLAUDE.local.md`.

## Commands

- `pip install -e ".[dev]" && pytest -q` (tests in `tests/`, no network).
- `docker compose up -d --build` — service `mcp` + `mongo`.

## Consumers — changes ship only from `main`

- **Downstream consumers install this package from GitHub `main`, unpinned.** A change reaches one only after it is pushed to `main` *and* the consumer image is rebuilt with `docker compose build --no-cache` (a normal rebuild keeps the cached pip layer). Keep `queries`/`agent` signatures backward compatible or change the consumer in step.
- The container runs code from `/app`, not site-packages (the Dockerfile installs only `__init__.py`, then copies the source). Scripts run inside it need `cd /app && PYTHONPATH=/app python …` or they fail with `ModuleNotFoundError: planning_center_mcp.sync`.

## Invariants

- **Lyrics come from Mongo, never the PCO API** (it has no lyric search). Two sources per song, both stored by `sync_pco_data`: PCO arrangement lyrics, and ProPresenter 7 `.pro` attachments (protobuf with RTF slide text, parsed in `propresenter.py` — no published schema). **Bump `PARSER_VERSION` after changing extraction** and re-sync; the cache is keyed on attachment id + `updated_at` and never re-reads otherwise.
- **`assign_tags_to_song` may replace a song's whole tag set** — read the current tags first (Mongo or `/services/v2/songs/{id}/tags`) and send them along with the new one.
- Agent calls to Ollama use `/api/chat` with `think: false`; the model comes from `AGENT_MODEL` (the hardcoded fallback in `agent.py` is overridden in every deployment).

## Traps

- **The PCO token can't create tags** — `create_song_tag` returns "Permission denied". It can assign existing tags; new ones are created in the PCO Services UI (Songs → Tags).
- One song (Gratitude) 422s on PCO's `/attachments/{id}/open` — PCO-side; it's logged and skipped.
- Nothing schedules `sync_pco_data`. Each consumer's Mongo drifts until someone syncs it.
- `llm.py` hardcodes `EMBED_MODEL` (`nomic-embed-text`) — that model must stay installed on the Ollama host.

## Review focus

- Signature or return-shape changes in `queries.py`/`agent.py` (downstream consumers import them).
- Tag writes that drop existing tags; extraction changes without a `PARSER_VERSION` bump.
