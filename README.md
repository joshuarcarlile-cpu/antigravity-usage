# Antigravity `/usage`

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-15%20passed-brightgreen.svg)](skills/usage/tests)

Real-time session telemetry, token breakdown, live IDE rate limits, and cost engine for **Google Antigravity**.

```text
┌──────────────────────────────────────────────────────────────┐
│ Google Antigravity Telemetry                                 │
│ Active Account: developer@example.com                        │
│ Target Session: 025c7515-7b3f-4cee-95be-aa616bf5f9da         │
│ Active Model: gemini-3.8-flash                               │
│ Provenance: ESTIMATED (0 reported, 97 estimated)             │
├──────────────────────────────────────────────────────────────┤
│ Rate Limits & Quotas (Antigravity Service):                  │
│ [Gemini Models]                                              │
│   Weekly Limit Remaining (resets in 5d 1h):                  │
│   [█████████████░░░] 81.4% remaining (18.6% used)            │
│   5-Hour Limit Remaining (resets in 2h 44m):                 │
│   [███████░░░░░░░░░] 44.9% remaining (55.1% used)            │
│                                                              │
│ [Claude and GPT models]                                      │
│   Weekly Limit Remaining (resets in 23h 22m):                │
│   [██████████░░░░░░] 64.4% remaining (35.6% used)            │
│   5-Hour Limit Remaining:                                    │
│   [████████████████] 100.0% remaining (0.0% used)            │
├──────────────────────────────────────────────────────────────┤
│ Context Occupancy:                                           │
│ [█░░░░░░░░░░░░░░░] 109,262 / 1,000,000 (10.9%)               │
│ Headroom Remaining: 890,738 tokens                           │
├──────────────────────────────────────────────────────────────┤
│ Token Breakdown:                                             │
│ Cumulative Input: 5,640,807 tokens                           │
│   Uncached Reads: 5,640,807 tokens                           │
│   Cached Reads: 0 tokens                                     │
│ Cumulative Output (incl thoughts): 8,355 tokens              │
│ Multimodal: 1 items (~258 tokens [approximate tiling])       │
├──────────────────────────────────────────────────────────────┤
│ Equivalent API Cost:                                         │
│ Equivalent USD: $4.2619                                      │
│ *Inferred cache rate. Quota synced via Antigravity.          │
├──────────────────────────────────────────────────────────────┤
│ Session Activity:                                            │
│ Wall Duration: 5264.0s                                       │
│ Model Turns / Steps: 97 turns / 201 steps                    │
│ Top Tools: run_command: 32, view_file: 21, list_dir: 12      │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/joshuarcarlile-cpu/antigravity-usage/main/install.ps1 | iex
```

### macOS / Linux (Bash)
```bash
curl -fsSL https://raw.githubusercontent.com/joshuarcarlile-cpu/antigravity-usage/main/install.sh | bash
```

Once installed, simply type `/usage` in any Antigravity conversation or run `usage` in your terminal.

---

## Usage

### In Antigravity Chat
Type `/usage` or `/cost` in any conversation:
- `/usage` — Show telemetry for the active session.
- `/usage --daily` — Aggregate today's usage across all sessions.

### In Terminal (CLI)
```bash
# Inspect the active session
usage

# Rolling daily total across all sessions today
usage --daily

# Output strict machine-readable JSON (v1.0.0)
usage --json

# Inspect a specific session ID
usage --conversation-id <id>
```

---

## Features

- **Live IDE Quota Sync**: Ingests real-time rate limits and reset countdowns directly from the Antigravity Language Server RPC.
- **Context Window & Headroom**: Visual progress bar tracking token occupancy and remaining tokens before compaction.
- **Dual-Path Accuracy**: Ingests official `usageMetadata` when available, with calibrated SentencePiece estimation fallback.
- **Exact Decimal Pricing**: Tiered pricing calculations using `decimal.Decimal` (zero floating-point drift).
- **100% Local & Private**: Operates entirely on local transcript logs and local IDE RPC port. Zero data leaves your machine.

---

## CLI Reference

| Flag | Description |
| :--- | :--- |
| `--daily` | Aggregate token consumption and cost across all sessions today |
| `--json` | Output machine-readable JSON contract (v1.0.0) |
| `--conversation-id <id>` | Inspect a specific session transcript |
| `--account <email>` | Filter or inspect specific user profile |
| `--reset-day <day>` | Set custom weekly reset day (e.g. `Wed`) |
| `--reset-time <time>` | Set custom weekly reset time (e.g. `18:00`) |
| `--save-reset` | Persist reset schedule to local config |
| `--width <n>` | Set terminal box column width (default: 64) |
| `--no-rate-limits` | Suppress rate limit section |

---

## Alternative Installation

<details>
<summary><b>As an Antigravity Global Plugin</b></summary>

Clone directly into your Antigravity plugins directory:

```bash
# Windows
git clone https://github.com/joshuarcarlile-cpu/antigravity-usage.git "$env:USERPROFILE\.gemini\config\plugins\antigravity-usage"

# macOS / Linux
git clone https://github.com/joshuarcarlile-cpu/antigravity-usage.git ~/.gemini/config/plugins/antigravity-usage
```
</details>

<details>
<summary><b>Project Workspace (Zero-Install for Teams)</b></summary>

Copy the skill and rule into your repo's `.agents/` folder:

```text
.agents/
├── rules/
│   └── telemetry.md
└── skills/
    └── usage/
        ├── SKILL.md
        └── scripts/
            ├── usage.py
            └── pricing.json
```
Anyone opening the repository in Antigravity gets `/usage` automatically with zero setup.
</details>

---

## Testing

Run the automated test suite verifying all mathematical invariants and schemas:

```bash
python -m unittest discover -s skills/usage/tests -p "test_*.py" -v
```

---

## License

[MIT License](LICENSE) © 2026 Joshua Carlile
