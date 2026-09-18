---
name: usage
description: View real-time token usage, context window occupancy, and equivalent API cost for the current Google Antigravity session or daily rolling activity. Activate this skill whenever the user asks for /usage, /cost, token consumption, context limits, or session expenses.
---

# Antigravity Telemetry & Usage Engine

This skill delivers real-time session telemetry, token breakdown (input, cached, output, multimodal), context window occupancy, and equivalent API cost calculations.

## Operational Workflow

When the user asks for `/usage`, `/cost`, or inquiries about token/context statistics:

1. **Deterministic Conversation ID Discovery**:
   - Search your system prompt for `Conversation ID: <uuid>` verbatim.
   - Locate `usage.py` (either in the local skill `./scripts/usage.py` or global install).
   - If found verbatim, execute with the pinned ID:
     ```bash
     python "<path-to-skill>/scripts/usage.py" --conversation-id <uuid>
     ```
   - If NOT found verbatim, DO NOT construct or guess one; simply run without the flag to allow auto-detection:
     ```bash
     python "<path-to-skill>/scripts/usage.py"
     ```

2. **Daily Aggregation**:
   - If the user asks for daily or cumulative daily usage (e.g. `/usage --daily`), add the `--daily` flag:
     ```bash
     python "<path-to-skill>/scripts/usage.py" --daily
     ```

3. **Machine-Readable JSON**:
   - If programmatic inspection is requested, add `--json`.

4. **Output Rendering**:
   - Present the rendered telemetry box directly to the user in a fenced code block so that the mechanical box borders and alignment are preserved.
