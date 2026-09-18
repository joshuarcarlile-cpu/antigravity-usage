#!/usr/bin/env python3
"""
Production-Grade /usage Telemetry Engine (v6 - Final)
Google Antigravity Telemetry & Cost Engine
"""

import sys
import os
import json
import re
import math
import time
import hashlib
import glob
import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCHEMA_VERSION = "1.0.0"
DEFAULT_BOX_WIDTH = 64
IN_FLIGHT_THRESHOLD_SECONDS = 60
CACHE_EXPIRY_SECONDS = 30 * 86400  # 30 days

# ANSI Colors
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_BLUE = "\033[34m"
ANSI_MAGENTA = "\033[35m"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences to calculate true visible width."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def get_user_home() -> str:
    """Resolve user home directory cross-platform."""
    return os.environ.get("USERPROFILE") or os.environ.get("HOME") or os.path.expanduser("~")


def get_brain_root() -> str:
    """Resolve brain root path cross-platform."""
    home = get_user_home()
    return os.path.join(home, ".gemini", "antigravity-ide", "brain")


def get_cache_dir() -> str:
    """Return local appdata cache directory cross-platform."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        cdir = os.path.join(base, "Antigravity", "telemetry_cache")
    else:
        home = get_user_home()
        cdir = os.path.join(home, ".cache", "antigravity", "telemetry_cache")
    os.makedirs(cdir, exist_ok=True)
    return cdir


def get_engine_hash(script_path: str, pricing_path: str) -> str:
    """Compute SHA-256 hash of usage.py and pricing.json for cache invalidation."""
    h = hashlib.sha256()
    for p in (script_path, pricing_path):
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def structural_tokenize(text: str) -> int:
    """
    Empirical structural tokenizer calibrated for Gemini SentencePiece behavior.
    Accurately accounts for words, subwords, punctuation, JSON structure, and indentation.
    """
    if not text:
        return 0
    tokens = 0
    pattern = re.compile(r'[a-zA-Z]+|\d+|[^\s\w]|\n|[ ]{2,4}')
    for m in pattern.finditer(text):
        s = m.group()
        if s.isalpha():
            n = len(s)
            if n <= 5:
                tokens += 1
            elif n <= 9:
                tokens += 2
            else:
                tokens += (n + 3) // 4
        elif s.isdigit():
            tokens += (len(s) + 2) // 3
        elif s.startswith(' ') and len(s) > 1:
            tokens += 1
        elif s == '\n':
            tokens += 1
        else:
            tokens += 1
    return tokens


def normalize_model_id(raw_model: str) -> str:
    """Normalize human-readable or raw model strings into canonical model IDs."""
    if not raw_model:
        return "gemini-3.8-flash"
    m = raw_model.strip().lower()
    if "3.8" in m and "flash" in m:
        return "gemini-3.8-flash"
    if "3.7" in m and "flash" in m:
        return "gemini-3.7-flash"
    if "2.5" in m and "flash-lite" in m or "flash lite" in m:
        return "gemini-2.5-flash-lite"
    if "2.5" in m and "pro" in m:
        return "gemini-2.5-pro"
    if "sonnet" in m:
        return "claude-sonnet-4-6"
    if "opus" in m:
        return "claude-opus-4-6"
    return m.replace(" ", "-")


def parse_timestamp_iso(ts_str: str) -> datetime:
    """Parse ISO 8601 UTC timestamp safely."""
    if not ts_str:
        return datetime.now(timezone.utc)
    ts = ts_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(timezone.utc)


def load_pricing(pricing_path: str) -> dict:
    """Load pricing configuration table."""
    if not os.path.exists(pricing_path):
        return {}
    try:
        with open(pricing_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def calculate_turn_cost(
    model_id: str,
    uncached_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    turn_time: datetime,
    pricing_config: dict
) -> tuple[Decimal | None, list[str]]:
    """
    Calculate turn cost using exact Decimal math.
    Returns (cost_decimal_or_None, assumed_rates_list).
    """
    model_entry = pricing_config.get(model_id)
    if not model_entry:
        return None, []

    windows = model_entry.get("windows", [])
    matched_window = None
    for w in windows:
        ef = w.get("effective_from")
        eu = w.get("effective_until")
        ef_dt = parse_timestamp_iso(ef) if ef else None
        eu_dt = parse_timestamp_iso(eu) if eu else None

        if ef_dt and turn_time < ef_dt:
            continue
        if eu_dt and turn_time > eu_dt:
            continue
        matched_window = w
        break

    if not matched_window:
        return None, []

    # Check long prompt threshold
    total_prompt = uncached_tokens + cached_tokens
    threshold = model_entry.get("long_prompt_threshold")
    is_long = threshold is not None and total_prompt > threshold

    if is_long and "long_input_rate" in matched_window:
        input_rate = Decimal(str(matched_window["long_input_rate"]))
        cached_rate = Decimal(str(matched_window.get("long_cached_rate", matched_window["cached_rate"])))
        output_rate = Decimal(str(matched_window["long_output_rate"]))
    else:
        input_rate = Decimal(str(matched_window["input_rate"]))
        cached_rate = Decimal(str(matched_window["cached_rate"]))
        output_rate = Decimal(str(matched_window["output_rate"]))

    assumed_rates = []
    if matched_window.get("cached_rate_assumed"):
        assumed_rates.append("cached_rate")

    million = Decimal("1000000")
    cost = (
        (Decimal(uncached_tokens) * input_rate / million) +
        (Decimal(cached_tokens) * cached_rate / million) +
        (Decimal(output_tokens) * output_rate / million)
    )
    return cost, assumed_rates


def find_most_recent_transcript() -> tuple[str | None, str | None]:
    """Auto-detect the most recently modified transcript file in the brain directory."""
    brain_root = get_brain_root()
    if not os.path.isdir(brain_root):
        return None, None

    pattern = os.path.join(brain_root, "*", ".system_generated", "logs", "transcript_full.jsonl")
    candidates = glob.glob(pattern)
    if not candidates:
        pattern_fallback = os.path.join(brain_root, "*", ".system_generated", "logs", "transcript.jsonl")
        candidates = glob.glob(pattern_fallback)

    if not candidates:
        return None, None

    best_file = max(candidates, key=os.path.getmtime)
    # Extract CID from path (parent of .system_generated)
    norm = os.path.normpath(best_file)
    parts = norm.split(os.sep)
    cid = None
    for i, p in enumerate(parts):
        if p == ".system_generated" and i > 0:
            cid = parts[i - 1]
            break
    return best_file, cid


def parse_transcript_stream(transcript_path: str, pricing_config: dict) -> dict:
    """
    Stream and evaluate a transcript JSONL file.
    Implements:
    - Linear single-pass structural tokenization
    - Context occupancy tracking
    - Exact Decimal pricing
    - Multimodal isolation
    - Incomplete trailing line tolerance
    """
    if not os.path.exists(transcript_path):
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    steps = []
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                steps.append(data)
            except json.JSONDecodeError:
                # In-flight or truncated line: ignore gracefully
                continue

    active_model = "gemini-3.8-flash"
    model_resolved = False

    tool_counts: dict[str, int] = {}
    timestamps: list[datetime] = []
    last_step_index = 0

    turns_data = []
    running_prompt_tokens = 0

    multimodal_items_total = 0
    multimodal_tokens_total = 0

    reconciliation_warnings: list[str] = []

    for step in steps:
        s_idx = step.get("step_index", last_step_index + 1)
        if s_idx > last_step_index:
            last_step_index = s_idx

        created_at_str = step.get("created_at")
        step_dt = parse_timestamp_iso(created_at_str)
        timestamps.append(step_dt)

        # Detect model changes in content or metadata
        content = step.get("content", "") or ""
        thinking = step.get("thinking", "") or ""
        combined_text = content + " " + thinking

        if "Model Selection" in combined_text:
            m = re.search(r"Model Selection`?\s+from\s+.+?\s+to\s+([A-Za-z0-9\.\-\s]+(?:\([^\)]+\))?)", combined_text)
            if m:
                target_model_str = m.group(1).strip()
                active_model = normalize_model_id(target_model_str)
                model_resolved = True

        # Tool calls inspection
        tool_calls = step.get("tool_calls", []) or []
        for tc in tool_calls:
            tname = tc.get("name", "unknown")
            tool_counts[tname] = tool_counts.get(tname, 0) + 1
            args = tc.get("args", {})
            args_str = str(args)

            # Multimodal detection
            if tname in ("generate_image", "browser_subagent") or any(ext in args_str.lower() for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                multimodal_items_total += 1
                dim_match = re.search(r'(\d{3,4})\s*[xX]\s*(\d{3,4})', args_str)
                if dim_match:
                    w, h = int(dim_match.group(1)), int(dim_match.group(2))
                    tiles = math.ceil(w / 768.0) * math.ceil(h / 768.0)
                    t_tokens = tiles * 258
                else:
                    t_tokens = 258  # lower bound
                multimodal_tokens_total += t_tokens

        stype = step.get("type")

        # Incrementally track prompt tokens for estimated turns (O(N) linear pass)
        if stype != "PLANNER_RESPONSE":
            if content:
                running_prompt_tokens += structural_tokenize(content)
        else:
            # Model Turn!
            turn_model = active_model
            usage_meta = step.get("usageMetadata")

            if usage_meta:
                mode = "reported"
                p_tokens = usage_meta.get("promptTokenCount", 0)
                cached_tokens = usage_meta.get("cachedContentTokenCount", 0)
                uncached_tokens = max(0, p_tokens - cached_tokens)
                c_tokens = usage_meta.get("candidatesTokenCount", 0)
                th_tokens = usage_meta.get("thoughtsTokenCount", 0)
                out_tokens = c_tokens + th_tokens
                reported_total = usage_meta.get("totalTokenCount", p_tokens + out_tokens)

                # Invariant reconciliation check
                computed_total = p_tokens + out_tokens
                if reported_total != computed_total:
                    reconciliation_warnings.append(
                        f"reported total ({reported_total}) != prompt + output ({computed_total})"
                    )

                turn_record = {
                    "mode": mode,
                    "model": turn_model,
                    "prompt_tokens": p_tokens,
                    "uncached_input": uncached_tokens,
                    "cached_input": cached_tokens,
                    "output_tokens": out_tokens,
                    "multimodal_items": multimodal_items_total,
                    "multimodal_tokens": multimodal_tokens_total,
                    "created_at": step_dt,
                    "local_date": step_dt.astimezone().strftime("%Y-%m-%d")
                }
                running_prompt_tokens = p_tokens + out_tokens
            else:
                mode = "estimated"
                estimated_prompt_tokens = running_prompt_tokens + multimodal_tokens_total
                estimated_output_tokens = structural_tokenize(thinking) + structural_tokenize(content)

                turn_record = {
                    "mode": mode,
                    "model": turn_model,
                    "prompt_tokens": estimated_prompt_tokens,
                    "uncached_input": estimated_prompt_tokens,
                    "cached_input": 0,
                    "output_tokens": estimated_output_tokens,
                    "multimodal_items": multimodal_items_total,
                    "multimodal_tokens": multimodal_tokens_total,
                    "created_at": step_dt,
                    "local_date": step_dt.astimezone().strftime("%Y-%m-%d")
                }
                running_prompt_tokens += estimated_output_tokens

            turns_data.append(turn_record)

    # Activity calculation
    total_steps = len(steps)
    total_turns = len(turns_data)
    reported_turns = sum(1 for t in turns_data if t["mode"] == "reported")
    estimated_turns = sum(1 for t in turns_data if t["mode"] == "estimated")

    if total_turns == 0:
        session_mode = "reported"
    elif reported_turns == total_turns:
        session_mode = "reported"
    elif estimated_turns == total_turns:
        session_mode = "estimated"
    else:
        session_mode = "mixed"

    # Wall duration
    if len(timestamps) >= 2:
        wall_duration = max(0.0, (timestamps[-1] - timestamps[0]).total_seconds())
    else:
        wall_duration = 0.0

    # Context occupancy: prompt tokens of latest complete turn
    if turns_data:
        occupancy_tokens = turns_data[-1]["prompt_tokens"]
    else:
        occupancy_tokens = 0

    model_cfg = pricing_config.get(active_model, {})
    limit_tokens = model_cfg.get("context_limit", 1000000)
    headroom = max(0, limit_tokens - occupancy_tokens)
    utilization_pct = round((occupancy_tokens / limit_tokens) * 100, 2) if limit_tokens > 0 else 0.0

    # Token aggregates
    cum_uncached = sum(t["uncached_input"] for t in turns_data)
    cum_cached = sum(t["cached_input"] for t in turns_data)
    cum_input = cum_uncached + cum_cached
    cum_output = sum(t["output_tokens"] for t in turns_data)

    # Pricing calculation
    total_cost_decimal = Decimal("0")
    priced_turns_count = 0
    all_assumed_rates = set()

    for t in turns_data:
        t_cost, assumed = calculate_turn_cost(
            model_id=t["model"],
            uncached_tokens=t["uncached_input"],
            cached_tokens=t["cached_input"],
            output_tokens=t["output_tokens"],
            turn_time=t["created_at"],
            pricing_config=pricing_config
        )
        if t_cost is not None:
            total_cost_decimal += t_cost
            priced_turns_count += 1
            all_assumed_rates.update(assumed)

    if priced_turns_count == 0:
        cost_usd = None
    else:
        cost_usd = float(total_cost_decimal.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

    return {
        "model": {
            "id": active_model,
            "resolved": model_resolved or (active_model in pricing_config)
        },
        "provenance": {
            "reported_turns": reported_turns,
            "estimated_turns": estimated_turns,
            "total_turns": total_turns,
            "mode": session_mode
        },
        "context_window": {
            "occupancy_tokens": occupancy_tokens,
            "limit_tokens": limit_tokens,
            "headroom_tokens": headroom,
            "utilization_pct": utilization_pct
        },
        "tokens": {
            "cumulative_input": cum_input,
            "uncached_input": cum_uncached,
            "cached_input": cum_cached,
            "cumulative_output": cum_output,
            "multimodal_items": multimodal_items_total,
            "multimodal_tokens": multimodal_tokens_total
        },
        "cost": {
            "equivalent_usd": cost_usd,
            "currency": "USD",
            "priced_turns": priced_turns_count,
            "total_turns": total_turns,
            "assumed_rates": sorted(list(all_assumed_rates))
        },
        "activity": {
            "wall_duration_seconds": round(wall_duration, 1),
            "last_step_index": last_step_index,
            "total_steps": total_steps,
            "model_turns": total_turns,
            "tool_counts": tool_counts
        },
        "reconciliation_warnings": reconciliation_warnings,
        "turn_dates": [t["local_date"] for t in turns_data]
    }


def manage_cache(
    cid: str,
    transcript_path: str,
    engine_hash: str,
    pricing_config: dict,
    no_cache: bool = False,
    refresh_cache: bool = False
) -> dict:
    """
    Manage multi-window cache with:
    - 60-second in-flight exclusion
    - Engine hash invalidation
    - Atomic JSON reads/writes
    """
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, f"{cid}.json")

    mtime = os.path.getmtime(transcript_path) if os.path.exists(transcript_path) else 0
    now = time.time()
    is_in_flight = (now - mtime) < IN_FLIGHT_THRESHOLD_SECONDS

    if not no_cache and not refresh_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if entry.get("engine_hash") == engine_hash and entry.get("mtime") == mtime:
                return entry["data"]
        except Exception:
            pass

    data = parse_transcript_stream(transcript_path, pricing_config)

    if not no_cache and not is_in_flight and os.path.exists(transcript_path):
        try:
            temp_cache = cache_file + f".tmp.{os.getpid()}"
            with open(temp_cache, "w", encoding="utf-8") as f:
                json.dump({
                    "conversation_id": cid,
                    "engine_hash": engine_hash,
                    "mtime": mtime,
                    "data": data
                }, f, indent=2)
            os.replace(temp_cache, cache_file)
        except Exception:
            pass

    return data


def compute_daily_totals(pricing_config: dict, engine_hash: str) -> dict:
    """
    Aggregate daily totals across all active sessions for today (local date).
    Cleans up cache files older than 30 days.
    """
    brain_root = get_brain_root()
    cache_dir = get_cache_dir()
    now = time.time()

    # 30-day cleanup
    try:
        for cfile in glob.glob(os.path.join(cache_dir, "*.json")):
            if now - os.path.getmtime(cfile) > CACHE_EXPIRY_SECONDS:
                try:
                    os.remove(cfile)
                except Exception:
                    pass
    except Exception:
        pass

    today_str = datetime.now().strftime("%Y-%m-%d")
    transcripts = glob.glob(os.path.join(brain_root, "*", ".system_generated", "logs", "transcript_full.jsonl"))

    daily_sessions = 0
    daily_tokens = 0
    daily_cost = Decimal("0")

    for t_path in transcripts:
        t_mtime = os.path.getmtime(t_path)
        if (now - t_mtime) > 48 * 3600:
            continue

        norm = os.path.normpath(t_path)
        parts = norm.split(os.sep)
        cid = "unknown"
        for i, p in enumerate(parts):
            if p == ".system_generated" and i > 0:
                cid = parts[i - 1]
                break

        try:
            sdata = manage_cache(cid, t_path, engine_hash, pricing_config)
            turn_dates = sdata.get("turn_dates", [])
            if any(d == today_str for d in turn_dates):
                daily_sessions += 1
                t_tokens = sdata["tokens"]["cumulative_input"] + sdata["tokens"]["cumulative_output"]
                daily_tokens += t_tokens
                if sdata["cost"]["equivalent_usd"] is not None:
                    daily_cost += Decimal(str(sdata["cost"]["equivalent_usd"]))
        except Exception:
            continue

    return {
        "active_sessions": daily_sessions,
        "cumulative_tokens": daily_tokens,
        "equivalent_usd": float(daily_cost.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    }


def format_value_with_overflow(val_str: str, max_len: int) -> str:
    """Enforces value-side overflow parenthetical dropping and truncation."""
    if len(val_str) <= max_len:
        return val_str

    curr = val_str
    while "(" in curr and len(curr) > max_len:
        idx = curr.rfind("(")
        curr = curr[:idx].strip()
        if len(curr) <= max_len:
            return curr

    if len(curr) > max_len:
        if max_len > 1:
            return curr[:max_len - 1] + "…"
        return curr[:max_len]
    return curr


def render_box(data: dict, width: int = DEFAULT_BOX_WIDTH, cid: str = "") -> str:
    """Render terminal card with dynamic box-drawing and ANSI-stripped width assertion."""
    inner_width = width - 4

    def make_border(left: str, mid: str, right: str) -> str:
        return left + (mid * (width - 2)) + right

    top_border = make_border("┌", "─", "┐")
    mid_border = make_border("├", "─", "┤")
    bot_border = make_border("└", "─", "┘")

    lines = [top_border]

    def add_row(content: str):
        vis_len = len(strip_ansi(content))
        if vis_len > inner_width:
            content = strip_ansi(content)[:inner_width]
            vis_len = len(content)
        pad = inner_width - vis_len
        line = f"│ {content}{' ' * pad} │"
        assert len(strip_ansi(line)) == width, f"Line width violation: {len(strip_ansi(line))} != {width}"
        lines.append(line)

    def add_pair(label: str, val_str: str, condensed_label: str = ""):
        avail_for_val = inner_width - len(label) - 1
        if avail_for_val < len(val_str) and condensed_label:
            label = condensed_label
            avail_for_val = inner_width - len(label) - 1

        fitted_val = format_value_with_overflow(val_str, max(0, avail_for_val))
        row = f"{label} {fitted_val}"
        add_row(row)

    # 1. Header Section
    model_name = data["model"]["id"]
    add_row(f"{ANSI_BOLD}{ANSI_CYAN}Google Antigravity Telemetry{ANSI_RESET}")
    if cid:
        cid_display = cid if len(cid) <= 36 else cid[:33] + "..."
        add_pair("Target Session:", cid_display)
    add_pair("Active Model:", f"{model_name}")

    prov = data["provenance"]
    prov_str = f"{prov['mode'].upper()} ({prov['reported_turns']} reported, {prov['estimated_turns']} estimated)"
    add_pair("Provenance:", prov_str)

    lines.append(mid_border)

    # 2. Context Window & Occupancy Gauge
    cw = data["context_window"]
    occupancy = cw["occupancy_tokens"]
    limit = cw["limit_tokens"]
    pct = cw["utilization_pct"]

    bar_width = 16
    filled = min(bar_width, int((pct / 100.0) * bar_width))
    bar = "█" * filled + "░" * (bar_width - filled)
    add_row(f"{ANSI_BOLD}Context Occupancy:{ANSI_RESET}")
    add_pair(f"[{bar}]", f"{occupancy:,} / {limit:,} ({pct:.1f}%)")
    add_pair("Headroom Remaining:", f"{cw['headroom_tokens']:,} tokens")

    lines.append(mid_border)

    # 3. Token Breakdown
    tok = data["tokens"]
    add_row(f"{ANSI_BOLD}Token Breakdown:{ANSI_RESET}")
    add_pair("Cumulative Input:", f"{tok['cumulative_input']:,} tokens")
    add_pair("  Uncached Reads:", f"{tok['uncached_input']:,} tokens")
    add_pair("  Cached Reads:", f"{tok['cached_input']:,} tokens")
    add_pair(
        "Cumulative Output (incl thoughts):",
        f"{tok['cumulative_output']:,} tokens",
        condensed_label="Cumulative Output (thoughts):"
    )

    mm_items = tok["multimodal_items"]
    mm_tokens = tok["multimodal_tokens"]
    if mm_items > 0:
        if prov["mode"] == "reported":
            mm_val = f"{mm_items} items (~{mm_tokens:,} tokens, subset of input)"
        else:
            mm_val = f"{mm_items} items (~{mm_tokens:,} tokens [approximate tiling])"
        add_pair("Multimodal:", mm_val)

    lines.append(mid_border)

    # 4. Cost Section
    cost = data["cost"]
    add_row(f"{ANSI_BOLD}Equivalent API Cost:{ANSI_RESET}")
    if cost["equivalent_usd"] is None:
        add_pair("Equivalent USD:", "Suppressed (unresolvable model)")
    else:
        priced = cost["priced_turns"]
        total_t = cost["total_turns"]
        cost_str = f"${cost['equivalent_usd']:.4f}"
        if priced < total_t:
            cost_str += f" ({priced}/{total_t} turns priced)"
        elif prov["mode"] == "mixed":
            cost_str += f"* (Mixed: {prov['reported_turns']} reported, {prov['estimated_turns']} estimated)"
        add_pair("Equivalent USD:", cost_str)

    if cost.get("assumed_rates"):
        add_row(f"{ANSI_DIM}*Inferred cache rate. Antigravity quotas not observable.{ANSI_RESET}")

    for warn in data.get("reconciliation_warnings", []):
        add_row(f"{ANSI_YELLOW}[Reconciliation Warning: {warn}]{ANSI_RESET}")

    lines.append(mid_border)

    # 5. Activity & Tool Invocations
    act = data["activity"]
    add_row(f"{ANSI_BOLD}Session Activity:{ANSI_RESET}")
    add_pair("Wall Duration:", f"{act['wall_duration_seconds']:.1f}s")
    add_pair("Model Turns / Steps:", f"{act['model_turns']} turns / {act['total_steps']} steps")

    tools = act.get("tool_counts", {})
    if tools:
        t_summary = ", ".join(f"{k}: {v}" for k, v in sorted(tools.items(), key=lambda x: x[1], reverse=True)[:4])
        add_pair("Top Tools:", t_summary)

    # 6. Daily Totals (if available)
    daily = data.get("daily_totals")
    if daily:
        lines.append(mid_border)
        add_row(f"{ANSI_BOLD}Daily Rolling Totals (Today):{ANSI_RESET}")
        add_pair("Active Sessions:", f"{daily['active_sessions']}")
        add_pair("Cumulative Tokens:", f"{daily['cumulative_tokens']:,}")
        add_pair("Daily Cost:", f"${daily['equivalent_usd']:.4f}")

    lines.append(bot_border)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Google Antigravity Production Telemetry & Cost Engine")
    parser.add_argument("--conversation-id", type=str, help="Conversation UUID to inspect")
    parser.add_argument("--transcript", type=str, help="Direct path to transcript file")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON v1.0.0")
    parser.add_argument("--daily", action="store_true", help="Include daily aggregation totals")
    parser.add_argument("--width", type=int, default=DEFAULT_BOX_WIDTH, help="Terminal box width (default 64)")
    parser.add_argument("--no-cache", action="store_true", help="Bypass reading and writing cache")
    parser.add_argument("--refresh-cache", action="store_true", help="Force cache refresh")
    parser.add_argument("--pricing", type=str, default=None, help="Custom path to pricing.json")

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    pricing_file = args.pricing if args.pricing else os.path.join(script_dir, "pricing.json")
    pricing_config = load_pricing(pricing_file)
    engine_hash = get_engine_hash(os.path.abspath(__file__), pricing_file)

    cid = args.conversation_id
    transcript_path = args.transcript
    auto_detected = False

    if not cid and not transcript_path:
        found_file, found_cid = find_most_recent_transcript()
        if found_file and found_cid:
            transcript_path = found_file
            cid = found_cid
            auto_detected = True
        else:
            if args.json:
                print(json.dumps({"error": "No transcript or conversation ID found"}, indent=2))
            else:
                print(f"{ANSI_RED}Error: No active conversation transcript found.{ANSI_RESET}", file=sys.stderr)
            sys.exit(1)

    if cid and not transcript_path:
        brain_root = get_brain_root()
        candidate_full = os.path.join(brain_root, cid, ".system_generated", "logs", "transcript_full.jsonl")
        candidate_std = os.path.join(brain_root, cid, ".system_generated", "logs", "transcript.jsonl")
        if os.path.exists(candidate_full):
            transcript_path = candidate_full
        elif os.path.exists(candidate_std):
            transcript_path = candidate_std
        else:
            if args.json:
                print(json.dumps({"error": f"Transcript for conversation {cid} not found"}, indent=2))
            else:
                print(f"{ANSI_RED}Error: Transcript for conversation {cid} not found.{ANSI_RESET}", file=sys.stderr)
            sys.exit(1)

    suppress_daily = bool(args.transcript)

    if args.no_cache or args.refresh_cache or suppress_daily:
        session_data = parse_transcript_stream(transcript_path, pricing_config)
    else:
        session_data = manage_cache(
            cid=cid or "unknown",
            transcript_path=transcript_path,
            engine_hash=engine_hash,
            pricing_config=pricing_config,
            no_cache=args.no_cache,
            refresh_cache=args.refresh_cache
        )

    if args.daily and not suppress_daily:
        daily_totals = compute_daily_totals(pricing_config, engine_hash)
    else:
        daily_totals = None

    session_data["daily_totals"] = daily_totals

    payload = {
        "schema_version": SCHEMA_VERSION,
        "conversation_id": cid or "isolated_transcript",
        "model": session_data["model"],
        "provenance": session_data["provenance"],
        "context_window": session_data["context_window"],
        "tokens": session_data["tokens"],
        "cost": session_data["cost"],
        "activity": session_data["activity"],
        "daily_totals": daily_totals
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if auto_detected:
            print(f"{ANSI_DIM}Target: {cid} (auto-detected most recent; use --conversation-id to pin){ANSI_RESET}\n")
        print(render_box(session_data, width=args.width, cid=cid or ""))


if __name__ == "__main__":
    main()
