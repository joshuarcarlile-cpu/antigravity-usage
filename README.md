# Antigravity `/usage` Telemetry Engine

A production-grade, mathematically verified telemetry and cost engine for **Google Antigravity**. Provides Claude-style visibility into real-time session token consumption, prefix caching efficiency, context window occupancy/headroom, and equivalent API cost calculations.

```text
┌──────────────────────────────────────────────────────────────┐
│ Google Antigravity Telemetry                                 │
│ Active Account: joshua.r.carlile@gmail.com                   │
│ Target Session: 025c7515-7b3f-4cee-95be-aa616bf5f9da         │
│ Active Model: gemini-3.8-flash                               │
│ Provenance: ESTIMATED (0 reported, 97 estimated)             │
├──────────────────────────────────────────────────────────────┤
│ Rate Limits & Quotas:                                        │
│ Weekly Limit (resets in 4d 17h (Tue 22:00 UTC)):             │
│ [████████░░░░░░░░] 47.2% (236.0M/500.0M tokens)              │
│ 5-Hour Limit (resets in 3h 3m):                              │
│ [████████████░░░░] 78.1% (39.1M/50.0M tokens)                │
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
│ *Inferred cache rate. Antigravity quotas not observable.     │
├──────────────────────────────────────────────────────────────┤
│ Session Activity:                                            │
│ Wall Duration: 5264.0s                                       │
│ Model Turns / Steps: 97 turns / 201 steps                    │
│ Top Tools: run_command: 32, view_file: 21, list_dir: 12, wr… │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Dual-Path Token Accounting**:
  - **Reported Path**: Automatically ingests official Gemini `usageMetadata` (`promptTokenCount`, `cachedContentTokenCount`, `candidatesTokenCount`, `thoughtsTokenCount`) when present.
  - **Estimated Path**: High-throughput linear single-pass structural tokenization calibrated for Gemini SentencePiece token distributions.
  - **Provenance Transparency**: Explicitly tags sessions as `REPORTED`, `ESTIMATED`, or `MIXED`.
- **Multimodal Isolation**:
  - Automatically isolates images and screenshots.
  - **Reported turns**: Preserves Gemini's native counts without double counting.
  - **Estimated turns**: Applies exact image tiling arithmetic ($\lceil w/768 \rceil \times \lceil h/768 \rceil \times 258$ tokens).
- **Exact Decimal Pricing & Tiered Thresholds**:
  - Eliminates IEEE 754 floating-point drift using Python `decimal.Decimal`.
  - Supports model-specific date windows and multi-tier prompt thresholds (e.g. `gemini-2.5-pro` 200k boundary).
- **Multi-Window Cache & In-Flight Exclusion**:
  - Concurrency-safe: transcripts modified $<60\text{s}$ ago are excluded from disk caching to prevent race conditions across active windows.
  - Automatic cache invalidation based on SHA-256 digests of engine code and pricing tables.
  - Automatic 30-day age cleanup on daily aggregation runs.
- **Mechanical Box Drawing**:
  - Strictly guarantees visible column width (default 64) with ANSI stripping and value-side overflow condensation.
- **Stable Machine-Readable JSON Contract (v1.0.0)**:
  - Clean `--json` mode with strict null semantics for automation pipelines.

---

## Quick Installation

### Option 1: One-Line Installer (Recommended)

#### Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/<your-org>/antigravity-usage/main/install.ps1 | iex
```
*(Or run `.\install.ps1` from a local clone).*

#### macOS / Linux (Bash):
```bash
curl -fsSL https://raw.githubusercontent.com/<your-org>/antigravity-usage/main/install.sh | bash
```
*(Or run `./install.sh` from a local clone).*

---

### Option 2: Antigravity Global Plugin

Clone or copy this repository directly into your Antigravity global plugins folder:

- **Windows**: `%USERPROFILE%\.gemini\config\plugins\antigravity-usage\`
- **macOS / Linux**: `~/.gemini/config/plugins/antigravity-usage/`

```bash
git clone https://github.com/<your-org>/antigravity-usage.git ~/.gemini/config/plugins/antigravity-usage
```

Antigravity will automatically discover the plugin, activate the rule in all conversations, and enable `/usage`.

---

### Option 3: Zero-Install Project Workspace

To enable `/usage` for anyone collaborating on a shared repository:

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
2. Commit and push. Anyone opening that repository in Antigravity gets `/usage` instantly with zero global configuration required.

---

## How to Use

### 1. In Antigravity Chat (IDE / CLI)
Type either slash command during any conversation:
```text
/usage
```
or
```text
/cost
```

### 2. Standalone Terminal Command

The installer exposes the `usage` CLI tool directly:

```powershell
# Inspect the most recent active session (auto-detects account and reset schedule)
usage

# Bind or inspect a specific user account
usage --account alice@dev.org

# Set an explicit weekly reset schedule for the active account and save it permanently
usage --reset-day Wed --reset-time 18:00 --save-reset

# Pin a specific conversation ID
usage --conversation-id 025c7515-7b3f-4cee-95be-aa616bf5f9da

# Include daily rolling totals across all sessions today
usage --daily

# Output strict machine-readable JSON (v1.0.0)
usage --json

# Customize terminal box width
usage --width 80
```

---

## Pricing Configuration (`pricing.json`)

Rates are decoupled from the core engine in `skills/usage/scripts/pricing.json`:

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
        "source": "Google Cloud Pricing (Introductory)",
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

## Running Automated Tests

Run the full automated test suite (verifies all 11 mathematical invariants, schema constraints, and edge cases):

```bash
python -m unittest discover -s skills/usage/tests -p "test_*.py" -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
