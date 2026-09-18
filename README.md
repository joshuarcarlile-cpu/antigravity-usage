# Antigravity `/usage` Telemetry & Cost Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-15%20passed-brightgreen.svg)](skills/usage/tests)
[![Antigravity](https://img.shields.io/badge/Antigravity-2.0+-purple.svg)](https://antigravity.google/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#installation)

A production-grade, mathematically verified telemetry and cost engine for **Google Antigravity**. Brings Claude-style visibility into real-time session token consumption, prefix caching efficiency, context window occupancy/headroom, live official IDE quota sync, and equivalent API cost calculations.

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

---

## Table of Contents

- [Why You Need This](#why-you-need-this)
- [Key Features](#key-features)
- [Installation](#installation)
  - [Option 1: One-Line Terminal Installer (Recommended)](#option-1-one-line-terminal-installer-recommended)
  - [Option 2: Antigravity Global Plugin](#option-2-antigravity-global-plugin)
  - [Option 3: Zero-Install Project Workspace](#option-3-zero-install-project-workspace)
  - [Option 4: Manual Local Clone](#option-4-manual-local-clone)
- [How to Use](#how-to-use)
  - [1. Inside Antigravity Chat](#1-inside-antigravity-chat)
  - [2. Standalone Terminal CLI](#2-standalone-terminal-cli)
- [Output Breakdown](#output-breakdown)
- [Architecture & Guarantees](#architecture--guarantees)
- [Pricing Configuration](#pricing-configuration)
- [Multi-Account & Reset Schedules](#multi-account--reset-schedules)
- [Automated Tests](#automated-tests)
- [Privacy & Security](#privacy--security)
- [Contributing](#contributing)
- [License](#license)

---

## Why You Need This

When building complex applications with Google Antigravity agents, conversations accumulate large amounts of context across dozens of model turns, tool calls, and subagents. 

Without telemetry:
- **Rate Limit Blindspots**: You can unexpectedly hit your 5-hour or weekly quota limit mid-task without warning.
- **Context Creep**: Large transcripts, knowledge items, and file reads silently fill your 1M or 2M token window, risking truncation.
- **Cost Invisibility**: Developers prototyping agentic workflows have no instant visibility into how much commercial API equivalent spend their sessions are generating.

**Antigravity `/usage` solves all of this.** It hooks directly into your local IDE's internal language server and session logs, giving you instantaneous, mathematically verified telemetry directly in chat or from your terminal.

---

## Key Features

- 🔄 **Live Antigravity Quota Service Ingestion**:
  - Automatically queries the local Antigravity Language Server RPC (`RetrieveUserQuotaSummary`) to extract 100% accurate, live official rate limits matching the IDE's "View Usage" popup.
  - Distinct tracking for both quota pools: **Gemini Models** and **Claude and GPT models**.
  - Displays real-time **Weekly Limit Remaining** and **5-Hour Limit Remaining** with live reset countdown timers (`in 5d 1h`, `in 2h 44m`).
  - Seamless fallback: If the language server is unreachable or idle, falls back to transcript summation anchored to user account reset schedules.

- 🧠 **Context Window Occupancy & Headroom**:
  - Visual ASCII occupancy bar calibrated to the active model's context window (e.g. 1,000,000 tokens for Flash, 2,000,000 for Pro).
  - Exact token count of the active context window alongside precise **Headroom Remaining** tokens before truncation occurs.

- ⚡ **Dual-Path Accurate Token Accounting**:
  - **Reported Path**: Ingests official Gemini `usageMetadata` (`promptTokenCount`, `cachedContentTokenCount`, `candidatesTokenCount`, `thoughtsTokenCount`) whenever reported by the backend.
  - **Estimated Path**: High-throughput linear single-pass structural tokenization calibrated for Gemini SentencePiece token distributions.
  - **Provenance Transparency**: Explicitly tags sessions as `REPORTED`, `ESTIMATED`, or `MIXED`.

- 🖼️ **Multimodal Token Isolation**:
  - Isolates images and screenshots from text.
  - **Reported turns**: Preserves Gemini's native counts without double counting.
  - **Estimated turns**: Applies exact image tiling arithmetic ($\lceil w/768 \rceil \times \lceil h/768 \rceil \times 258$ tokens).

- 💰 **Exact Decimal Pricing & Tiered Thresholds**:
  - Zero IEEE 754 floating-point drift using Python's `decimal.Decimal`.
  - Supports model-specific date windows and multi-tier prompt thresholds (e.g. `gemini-2.5-pro` 200k boundary).

- 🔒 **Multi-Window Cache & In-Flight Concurrency Protection**:
  - Concurrency-safe: transcripts modified $<60\text{s}$ ago are excluded from disk caching to prevent race conditions across active windows.
  - Automatic cache invalidation based on SHA-256 digests of engine code and pricing tables.
  - Automatic 30-day age cleanup on daily aggregation runs.

- 📐 **Mechanical Box Drawing**:
  - Strictly guarantees visible column width (default 64) with ANSI code stripping and value-side overflow condensation.

- 🤖 **Stable Machine-Readable JSON Contract (v1.0.0)**:
  - Clean `--json` mode with strict null semantics for CI/CD, automation scripts, and custom dashboards.

---

## Installation

### Option 1: One-Line Terminal Installer (Recommended)

#### Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/joshuarcarlile-cpu/antigravity-usage/main/install.ps1 | iex
```

#### macOS / Linux (Bash):
```bash
curl -fsSL https://raw.githubusercontent.com/joshuarcarlile-cpu/antigravity-usage/main/install.sh | bash
```

*The installer automatically configures the Antigravity global plugin, links the `usage` CLI executable into your PATH, and runs the verification suite.*

---

### Option 2: Antigravity Global Plugin

Clone this repository directly into your Antigravity global plugins directory:

#### Windows:
```powershell
git clone https://github.com/joshuarcarlile-cpu/antigravity-usage.git "$env:USERPROFILE\.gemini\config\plugins\antigravity-usage"
```

#### macOS / Linux:
```bash
git clone https://github.com/joshuarcarlile-cpu/antigravity-usage.git ~/.gemini/config/plugins/antigravity-usage
```

Antigravity will automatically discover the plugin, register the telemetry rule in all conversations, and enable `/usage`.

---

### Option 3: Zero-Install Project Workspace

To enable `/usage` for anyone collaborating on a shared repository without requiring them to install global plugins:

1. Copy the contents into your project's `.agents/` folder:
   ```text
   <your-project-root>/
   └── .agents/
       ├── rules/
       │   └── telemetry.md
       └── skills/
           └── usage/
               ├── SKILL.md
               └── scripts/
                   ├── usage.py
                   └── pricing.json
   ```
2. Commit and push. Anyone opening that repository in Antigravity gets `/usage` instantly with zero setup required.

---

### Option 4: Manual Local Clone

```bash
git clone https://github.com/joshuarcarlile-cpu/antigravity-usage.git
cd antigravity-usage

# On Windows:
.\install.ps1

# On macOS / Linux:
chmod +x ./install.sh && ./install.sh
```

---

## How to Use

### 1. Inside Antigravity Chat

In any conversation in the Antigravity IDE or CLI, simply type:

```text
/usage
```
or
```text
/cost
```

To see cumulative rolling usage across all sessions today:
```text
/usage --daily
```

---

### 2. Standalone Terminal CLI

The installer exposes the `usage` CLI tool directly in your terminal:

```bash
# Inspect the most recent active session (auto-detects active account and reset schedule)
usage

# Bind or inspect a specific user account
usage --account user@domain.com

# Set an explicit weekly reset schedule for the active account and save it permanently
usage --reset-day Wed --reset-time 18:00 --save-reset

# Inspect a specific conversation ID
usage --conversation-id 025c7515-7b3f-4cee-95be-aa616bf5f9da

# Include daily rolling totals across all sessions today
usage --daily

# Output strict machine-readable JSON (v1.0.0)
usage --json

# Customize terminal box width (e.g. 80 columns)
usage --width 80

# Exclude rate limit section if you only want token metrics
usage --no-rate-limits
```

---

## Output Breakdown

| Section | Description |
| :--- | :--- |
| **Header** | Displays active user account, session UUID, active model, and data provenance (`REPORTED`, `ESTIMATED`, or `MIXED`). |
| **Rate Limits & Quotas** | Live official Antigravity Language Server quotas for both **Gemini Models** and **Claude & GPT models**, including weekly/5-hour bars and exact reset countdowns. |
| **Context Occupancy** | Current context window fill level (e.g. `109,262 / 1,000,000 (10.9%)`) and exact **Headroom Remaining** tokens before compaction. |
| **Token Breakdown** | Granular input breakdown (Uncached vs. Cached reads), cumulative output tokens (including model thought steps), and multimodal item count. |
| **Equivalent API Cost** | Commercial API equivalent expenditure calculated with `decimal.Decimal` using active pricing tables and prompt boundary tiers. |
| **Session Activity** | Total wall-clock conversation duration, model turns, agent step count, and top tool execution frequencies. |

---

## Architecture & Guarantees

```
┌─────────────────────────────────┐
│     Google Antigravity IDE      │
│  (Session Transcripts & Logs)   │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐     RPC      ┌─────────────────────────────────┐
│   Antigravity Language Server   │ ◄──────────► │    Live Service Quota Sync      │
│      (Local Port RPC)           │              │ (Weekly & 5-Hour Limit Engine)  │
└─────────────────────────────────┘              └────────────────┬────────────────┘
                                                                  │
                                                                  ▼
┌─────────────────────────────────┐              ┌─────────────────────────────────┐
│      Dual-Path Tokenizer        │ ───────────► │      Exact Pricing Engine       │
│  • Official usageMetadata       │              │  • decimal.Decimal Precision    │
│  • Calibrated SentencePiece     │              │  • Model-specific Date Windows  │
│  • Multimodal Tiling (258/tile) │              │  • 200k Tiered Boundaries       │
└─────────────────────────────────┘              └────────────────┬────────────────┘
                                                                  │
                                                                  ▼
                                                 ┌─────────────────────────────────┐
                                                 │   Mechanical Terminal Box       │
                                                 │   • ANSI Strip & Width Lock     │
                                                 │   • v1.0.0 JSON Serialization   │
                                                 └─────────────────────────────────┘
```

### Key Mathematical & Architectural Invariants:
1. **Zero Double-Counting**: If Gemini returns official `usageMetadata`, text and image prompt counts are ingested directly. Multimodal estimation is only applied on estimated turns.
2. **Deterministic Calibration**: Single-pass structural tokenization calibrated with strict manifest tolerances for code, markdown, and conversational text.
3. **Strict Concurrency Safety**: In-flight sessions modified $<60\text{s}$ ago bypass disk caching to ensure real-time accuracy during active model responses.
4. **Resilient Offline Fallback**: If the local IDE RPC port is unavailable, the engine gracefully transitions to transcript-based quota estimation without crashing or hanging.

---

## Pricing Configuration

Pricing rates are completely decoupled from core engine logic in [`pricing.json`](skills/usage/scripts/pricing.json):

```json
{
  "gemini-3.8-flash": {
    "context_limit": 1000000,
    "windows": [
      {
        "effective_from": null,
        "effective_until": "2026-12-31T23:59:59Z",
        "input_rate": 0.75,
        "cached_rate": 0.075,
        "cached_rate_assumed": true,
        "output_rate": 3.75,
        "source": "Google Cloud Pricing",
        "verified_on": "2026-09-17"
      }
    ]
  },
  "gemini-2.5-pro": {
    "context_limit": 2000000,
    "long_prompt_threshold": 200000,
    "windows": [
      {
        "effective_from": null,
        "effective_until": null,
        "input_rate": 1.25,
        "cached_rate": 0.125,
        "output_rate": 10.00,
        "long_input_rate": 2.50,
        "long_cached_rate": 0.25,
        "long_output_rate": 15.00,
        "source": "ai.google.dev",
        "verified_on": "2026-09-17"
      }
    ]
  }
}
```

---

## Multi-Account & Reset Schedules

Antigravity accounts often have differing weekly quota reset windows depending on when subscription tiers were initialized.

The engine stores account-specific preferences locally in `~/.gemini/antigravity-ide/user_accounts.json`:

```bash
# View usage for a secondary account
usage --account work-profile@company.com

# Pin custom reset schedule (e.g. Friday at 15:00 UTC)
usage --account work-profile@company.com --reset-day Fri --reset-time 15:00 --save-reset
```

---

## Automated Tests

The engine includes a full test suite verifying all 15 core architectural invariants, quota rendering, JSON contracts, and mathematical precision:

```bash
python -m unittest discover -s skills/usage/tests -p "test_*.py" -v
```

Output:
```text
test_account_resolution_and_reset_schedule ... ok
test_cost_formula_reconciliation ... ok
test_fixture_isolation ... ok
test_inflight_multiwindow_cache_exclusion ... ok
test_json_schema_contract ... ok
test_live_service_quota_rendering ... ok
test_mechanical_line_width ... ok
test_mixed_provenance_cost_annotation ... ok
test_model_specific_prompt_threshold ... ok
test_multi_scale_calibration ... ok
test_partial_cost_turn_annotation ... ok
test_rate_limits_weekly_and_five_hour_order ... ok
test_render_box_active_account ... ok
test_reported_multimodal_does_not_double_count ... ok
test_truncated_trailing_line ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.030s

OK
```

---

## Privacy & Security

- **100% Local Execution**: The telemetry engine runs exclusively on your local machine.
- **Zero External Telemetry**: No tokens, conversation snippets, file paths, or usage metrics are ever sent to third-party endpoints or external servers.
- **Read-Only Inspection**: Inspects local Antigravity transcript JSONL logs and queries the local IDE Language Server RPC on `127.0.0.1`.
- **Non-Invasive**: Does not alter or touch your Antigravity conversation history or agent configurations.

---

## Contributing

Contributions are welcome! If you'd like to contribute:

1. Fork the repository (`https://github.com/joshuarcarlile-cpu/antigravity-usage`).
2. Create a feature branch (`git checkout -b feat/my-feature`).
3. Ensure all tests pass (`python -m unittest discover -s skills/usage/tests -p "test_*.py"`).
4. Commit your changes (`git commit -m 'feat: add support for new model'`).
5. Push to your branch (`git push origin feat/my-feature`).
6. Open a Pull Request.

---

## License

Distributed under the [MIT License](LICENSE). Copyright &copy; 2026 Joshua Carlile.
