---
name: usage
description: View real-time token usage, context window occupancy, rate limits, and API cost. Activate on /usage or /cost.
---

# Antigravity Telemetry Engine

Execute the CLI wrapper directly without exploratory file inspection:
- **Compact Summary (Default)**: `usage --compact` (or with pinned session: `usage --compact --conversation-id <uuid>`)
- **Full Box Card**: `usage` (or `usage --conversation-id <uuid>`)
- **Daily Aggregation**: `usage --daily` (or `usage --compact --daily`)
- **Machine JSON**: `usage --json`

Render the CLI stdout verbatim in a fenced code block (` ```text `) without duplicate text repetition.
