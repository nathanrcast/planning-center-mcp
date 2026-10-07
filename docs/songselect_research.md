# CCLI SongSelect integration — research

Researched 2026-09-20; not pursued.

## Context
Research: is there a SongSelect API, and does an MCP exist? Goal: CCLI search working with the existing planning-center MCP.

## Findings
- Official SongSelect Partner API exists (OIDC/OAuth2 + subscription key, docs on Postman) but the partner program is **retired**; no new partners (songselect.ccli.com/about/apipartners). Not usable by us.
- No SongSelect MCP found (GitHub search "songselect mcp" = 0 repos; web search nothing). No credible public unofficial scraper either.
- PCO's SongSelect integration is UI-only (stores CCLI creds, imports lyrics/charts); not exposed in the PCO API.

## Recommended approach (if pursued)
1. Cheap first: PCO Song objects carry `ccli_number`; extend/use planning-center MCP to surface it and flag songs missing one. Zero new dependencies.
2. Search: personal-use MCP driving songselect.ccli.com with the user's own login (Playwright/session cookie) — read-only search returning title, authors, CCLI #, key/tempo. Fragile, ToS-gray; keep to metadata, no lyric/chart bulk download, low rate.
3. Alternative: email CCLI partner contact to ask for an exception; low odds.

## Verification
Search a known song (e.g. "Goodness of God") and confirm CCLI # matches the PCO song record.
