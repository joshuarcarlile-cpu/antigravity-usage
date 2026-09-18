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
import base64
import hashlib
import glob
import argparse
import urllib.request
import ssl
from datetime import datetime, timezone, timedelta
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


def get_brain_roots() -> list:
    """
    Resolve all potential brain root paths cross-platform and deduplicate them.
    Supports Antigravity CLI, Antigravity IDE, custom env vars, and standard OS appdata locations.
    """
    home = get_user_home()
    candidates = []

    # 1. Environment variables
    for env_key in ("ANTIGRAVITY_BRAIN_DIR", "GEMINI_BRAIN_DIR"):
        v = os.environ.get(env_key)
        if v and os.path.isdir(v):
            candidates.append(v)

    for env_key in ("ANTIGRAVITY_DATA_DIR", "GEMINI_DATA_DIR", "GEMINI_HOME", "ANTIGRAVITY_HOME"):
        v = os.environ.get(env_key)
        if v:
            candidates.append(os.path.join(v, "brain"))
            candidates.append(os.path.join(v, "antigravity", "brain"))
            candidates.append(os.path.join(v, "antigravity-ide", "brain"))

    # 2. Standard ~/.gemini and ~/.antigravity locations
    candidates.extend([
        os.path.join(home, ".gemini", "antigravity", "brain"),
        os.path.join(home, ".gemini", "antigravity-ide", "brain"),
        os.path.join(home, ".antigravity", "brain"),
        os.path.join(home, ".gemini", "brain"),
        os.path.join(home, ".antigravity-ide", "brain"),
    ])

    # 3. OS-specific standard application data locations
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        app_data = os.environ.get("APPDATA")
        if local_app_data:
            candidates.extend([
                os.path.join(local_app_data, "Antigravity", "brain"),
                os.path.join(local_app_data, "antigravity", "brain"),
                os.path.join(local_app_data, "Google", "Antigravity", "brain"),
                os.path.join(local_app_data, "Programs", "Antigravity", "brain"),
            ])
        if app_data:
            candidates.extend([
                os.path.join(app_data, "Antigravity", "brain"),
                os.path.join(app_data, "antigravity", "brain"),
            ])
    elif sys.platform == "darwin":
        candidates.extend([
            os.path.join(home, "Library", "Application Support", "Antigravity", "brain"),
            os.path.join(home, "Library", "Application Support", "Google", "Antigravity", "brain"),
        ])
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
        xdg_config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        candidates.extend([
            os.path.join(xdg_data, "antigravity", "brain"),
            os.path.join(xdg_config, "antigravity", "brain"),
            os.path.join(home, ".local", "share", "antigravity", "brain"),
        ])

    # Canonicalize, filter existing, and preserve order while deduplicating
    existing = []
    seen = set()
    for p in candidates:
        if p and os.path.isdir(p):
            norm = os.path.normcase(os.path.abspath(p))
            if norm not in seen:
                seen.add(norm)
                existing.append(os.path.abspath(p))

    # If no existing directories found yet, return primary default
    if not existing:
        return [os.path.join(home, ".gemini", "antigravity", "brain")]
    return existing


def get_brain_root() -> str:
    """Resolve active brain root path cross-platform."""
    return get_brain_roots()[0]


def find_all_transcripts() -> dict:
    """
    Locate all unique conversation transcripts across all brain roots.
    Returns dict mapping conversation_id -> transcript_path.
    Prefers transcript_full.jsonl over transcript.jsonl.
    """
    found = {}
    for root in get_brain_roots():
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except Exception:
            continue
        for entry in entries:
            cdir = os.path.join(root, entry)
            if not os.path.isdir(cdir):
                continue
            logs_dir = os.path.join(cdir, ".system_generated", "logs")
            if not os.path.isdir(logs_dir):
                continue
            t_full = os.path.join(logs_dir, "transcript_full.jsonl")
            t_std = os.path.join(logs_dir, "transcript.jsonl")
            chosen = None
            if os.path.exists(t_full):
                chosen = t_full
            elif os.path.exists(t_std):
                chosen = t_std
            if chosen:
                if entry in found:
                    try:
                        if os.path.getmtime(chosen) > os.path.getmtime(found[entry]):
                            found[entry] = chosen
                    except Exception:
                        pass
                else:
                    found[entry] = chosen
    return found


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


DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_NAME_MAP = {
    "mon": "Mon", "monday": "Mon",
    "tue": "Tue", "tues": "Tue", "tuesday": "Tue",
    "wed": "Wed", "wednesday": "Wed",
    "thu": "Thu", "thur": "Thu", "thurs": "Thu", "thursday": "Thu",
    "fri": "Fri", "friday": "Fri",
    "sat": "Sat", "saturday": "Sat",
    "sun": "Sun", "sunday": "Sun"
}


def get_active_account(cli_account: str = None) -> dict:
    """
    Resolve active user account identity.
    Priority:
    1. Explicit CLI argument (--account)
    2. Environment variable (GEMINI_ACCOUNT or ANTIGRAVITY_ACCOUNT)
    3. ~/.gemini/google_accounts.json ('active' key)
    4. ~/.gemini/oauth_creds.json (id_token JWT email claim)
    5. OS username fallback
    """
    if cli_account and cli_account.strip():
        return {
            "account": cli_account.strip(),
            "source": "cli",
            "name": None
        }

    env_acc = os.environ.get("GEMINI_ACCOUNT") or os.environ.get("ANTIGRAVITY_ACCOUNT")
    if env_acc and env_acc.strip():
        return {
            "account": env_acc.strip(),
            "source": "env",
            "name": None
        }

    home = get_user_home()
    for config_dir in (os.path.join(home, ".gemini"), os.path.join(home, ".antigravity")):
        ga_path = os.path.join(config_dir, "google_accounts.json")
        if os.path.exists(ga_path):
            try:
                with open(ga_path, "r", encoding="utf-8") as f:
                    ga_data = json.load(f)
                active_email = ga_data.get("active")
                if active_email and str(active_email).strip():
                    return {
                        "account": str(active_email).strip(),
                        "source": "google_accounts.json",
                        "name": None
                    }
            except Exception:
                pass

        oauth_path = os.path.join(config_dir, "oauth_creds.json")
        if os.path.exists(oauth_path):
            try:
                with open(oauth_path, "r", encoding="utf-8") as f:
                    oauth_data = json.load(f)
                id_token = oauth_data.get("id_token")
                if id_token and "." in id_token:
                    parts = id_token.split(".")
                    if len(parts) >= 2:
                        payload_b64 = parts[1]
                        rem = len(payload_b64) % 4
                        if rem > 0:
                            payload_b64 += "=" * (4 - rem)
                        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
                        payload = json.loads(payload_json)
                        email = payload.get("email")
                        name = payload.get("name")
                        if email and str(email).strip():
                            return {
                                "account": str(email).strip(),
                                "source": "oauth_creds.json",
                                "name": name
                            }
            except Exception:
                pass

    sys_user = os.environ.get("USERNAME") or os.environ.get("USER") or "default_user"
    return {
        "account": str(sys_user).strip(),
        "source": "system",
        "name": None
    }


def normalize_reset_day(day_str: str) -> str:
    """Normalize day string to standard 3-letter title case (e.g. 'mon' -> 'Mon')."""
    if not day_str:
        return "Sun"
    cleaned = day_str.strip().lower()
    return DAY_NAME_MAP.get(cleaned, "Sun")


def normalize_reset_time(time_str: str) -> str:
    """Normalize user time input into HH:MM 24-hour UTC format."""
    if not time_str:
        return "00:00"
    raw = time_str.strip().lower()
    am = "am" in raw
    pm = "pm" in raw
    clean = re.sub(r'[^0-9:]', '', raw)

    if ":" in clean:
        parts = clean.split(":")
        h = int(parts[0]) if parts[0].isdigit() else 0
        m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    else:
        h = int(clean) if clean.isdigit() else 0
        m = 0

    if pm and h < 12:
        h += 12
    if am and h == 12:
        h = 0
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    return f"{h:02d}:{m:02d}"


def get_account_resets_config_path() -> str:
    home = get_user_home()
    p1 = os.path.join(home, ".gemini", "account_resets.json")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(home, ".antigravity", "account_resets.json")
    if os.path.exists(p2):
        return p2
    return p1


def load_user_account_resets() -> dict:
    cpath = get_account_resets_config_path()
    if os.path.exists(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_user_account_reset(account: str, reset_day: str, reset_time_utc: str) -> bool:
    cpath = get_account_resets_config_path()
    try:
        os.makedirs(os.path.dirname(cpath), exist_ok=True)
        resets = load_user_account_resets()
        resets[account.strip().lower()] = {
            "reset_day": reset_day,
            "reset_time_utc": reset_time_utc,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(resets, f, indent=2)
        return True
    except Exception:
        return False


def resolve_account_reset_schedule(
    account: str,
    pricing_config: dict,
    cli_day: str = None,
    cli_time: str = None
) -> dict:
    """
    Resolve user account weekly reset schedule.
    Ties rate limits directly to the user's specific account.
    Hierarchy:
    1. CLI overrides (--reset-day, --reset-time)
    2. Local user config (~/.gemini/account_resets.json)
    3. pricing.json rate_limits.account_resets[account]
    4. Deterministic SHA-256 account derivation (so different accounts never reset at the same time)
    """
    acc_norm = account.strip().lower()

    if cli_day or cli_time:
        day = normalize_reset_day(cli_day) if cli_day else "Sun"
        t_utc = normalize_reset_time(cli_time) if cli_time else "00:00"
        return {
            "account": account,
            "reset_day": day,
            "reset_time_utc": t_utc,
            "source": "cli_override",
            "is_custom": True
        }

    # Check ~/.gemini/account_resets.json
    user_resets = load_user_account_resets()
    if acc_norm in user_resets:
        cfg = user_resets[acc_norm]
        return {
            "account": account,
            "reset_day": normalize_reset_day(cfg.get("reset_day")),
            "reset_time_utc": normalize_reset_time(cfg.get("reset_time_utc")),
            "source": "user_config",
            "is_custom": True
        }

    # Check pricing.json rate_limits.account_resets or top-level account_resets
    rl_cfg = pricing_config.get("rate_limits", {})
    acct_resets = rl_cfg.get("account_resets") or pricing_config.get("account_resets", {})
    if isinstance(acct_resets, dict) and acc_norm in acct_resets:
        cfg = acct_resets[acc_norm]
        return {
            "account": account,
            "reset_day": normalize_reset_day(cfg.get("reset_day")),
            "reset_time_utc": normalize_reset_time(cfg.get("reset_time_utc")),
            "source": "pricing_config",
            "is_custom": True
        }

    # Deterministic account derivation (ensures independent, staggered reset for every account)
    h = hashlib.sha256(acc_norm.encode("utf-8")).digest()
    day = DAYS_OF_WEEK[h[0] % 7]
    hour = h[1] % 24
    minute = (h[2] % 4) * 15
    t_utc = f"{hour:02d}:{minute:02d}"
    return {
        "account": account,
        "reset_day": day,
        "reset_time_utc": t_utc,
        "source": "account_hash",
        "is_custom": False
    }


def compute_account_weekly_window(reset_day: str, reset_time_utc: str, now: datetime = None):
    """
    Given a user account's reset day and time (UTC), compute:
    - next_reset datetime (UTC)
    - last_reset datetime (UTC, 7 days prior to next_reset)
    - countdown string (e.g. 'in 4d 18h (Tue 22:00 UTC)')
    """
    now = now or datetime.now(timezone.utc)
    day_idx = DAYS_OF_WEEK.index(reset_day) if reset_day in DAYS_OF_WEEK else 6
    h_str, m_str = reset_time_utc.split(":")
    target_hour = int(h_str)
    target_minute = int(m_str)

    days_ahead = (day_idx - now.weekday()) % 7
    if days_ahead == 0:
        target_today = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if now >= target_today:
            days_ahead = 7

    next_reset = (now + timedelta(days=days_ahead)).replace(
        hour=target_hour, minute=target_minute, second=0, microsecond=0
    )
    last_reset = next_reset - timedelta(days=7)
    diff = next_reset - now
    days = diff.days
    hours = diff.seconds // 3600
    resets_str = f"in {days}d {hours}h ({reset_day} {reset_time_utc} UTC)"
    return next_reset, last_reset, resets_str


def fetch_live_antigravity_quota() -> dict:
    """
    Query the active Antigravity Language Server via local connect-rpc
    to obtain real-time, official rate limit and quota bucket summaries.
    """
    home = get_user_home()
    search_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), "Antigravity IDE", "logs"),
        os.path.join(os.environ.get("APPDATA", ""), "antigravity", "logs"),
        os.path.join(home, ".config", "Antigravity IDE", "logs"),
        os.path.join(home, "Library", "Application Support", "Antigravity IDE", "logs"),
    ]

    log_candidates = []
    for sdir in search_dirs:
        if os.path.exists(sdir):
            for log_file in glob.glob(os.path.join(sdir, "*", "ls-main.log")):
                log_candidates.append(log_file)

    if not log_candidates:
        return None

    log_candidates.sort(key=os.path.getmtime, reverse=True)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for log_path in log_candidates[:3]:
        port = None
        csrf_token = None
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                for _ in range(200):
                    line = f.readline()
                    if not line:
                        break
                    if not csrf_token:
                        m_csrf = re.search(r"--csrf_token\s+([a-f0-9\-]+)", line)
                        if m_csrf:
                            csrf_token = m_csrf.group(1)
                    if not port:
                        m_port = re.search(r"LS started on port\s+(\d+)", line)
                        if m_port:
                            port = int(m_port.group(1))
                    if port and csrf_token:
                        break
        except Exception:
            continue

        if not port or not csrf_token:
            continue

        url = f"https://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
        headers = {
            "Content-Type": "application/json",
            "x-codeium-csrf-token": csrf_token,
            "Connect-Protocol-Version": "1"
        }
        data = json.dumps({"forceRefresh": True}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=1.5) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8", errors="ignore")
                    payload = json.loads(raw)
                    groups = payload.get("response", {}).get("groups", [])
                    if groups:
                        return {
                            "source": "language_server_live",
                            "port": port,
                            "groups": groups
                        }
        except Exception:
            continue

    return None


def format_reset_countdown(iso_str: str, now: datetime = None, rem_frac: float = 0.0) -> str:
    """Format an ISO timestamp into Antigravity UI-style reset countdown (e.g. 'in 5d 1h', 'in 5d', or 'in 2h 47m')."""
    if not iso_str or rem_frac >= 0.9999:
        return "idle"
    now = now or datetime.now(timezone.utc)
    iso_clean = iso_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_clean)
    except Exception:
        return "idle"
    diff = dt - now
    total_secs = int(diff.total_seconds())
    if total_secs <= 0:
        return "idle"
    days = diff.days
    if days > 0:
        rem_secs = total_secs - (days * 86400)
        hours = rem_secs // 3600
        if hours > 0:
            return f"in {days}d {hours}h"
        else:
            return f"in {days}d"
    else:
        hours = total_secs // 3600
        mins = round((total_secs % 3600) / 60)
        if mins >= 60:
            hours += 1
            mins = 0
        if hours > 0:
            return f"in {hours}h {mins}m"
        else:
            return f"in {mins}m"


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
    """Auto-detect the most recently modified transcript file across all brain directories."""
    all_trans = find_all_transcripts()
    if not all_trans:
        return None, None
    try:
        best_cid = max(all_trans.keys(), key=lambda k: os.path.getmtime(all_trans[k]))
        return all_trans[best_cid], best_cid
    except Exception:
        first_cid = next(iter(all_trans))
        return all_trans[first_cid], first_cid


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
        "turn_dates": [t["local_date"] for t in turns_data],
        "turns_summary": [{"ts": t["created_at"].isoformat(), "tokens": t["prompt_tokens"] + t["output_tokens"]} for t in turns_data]
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


def compute_rate_limits(
    pricing_config: dict,
    engine_hash: str,
    account_info: dict = None,
    cli_day: str = None,
    cli_time: str = None
) -> dict:
    """
    Compute rolling 5-hour session limit and weekly limit against configured quotas.
    Priority 1: Live Antigravity Language Server connect-rpc query (official ground truth).
    Priority 2: Offline estimated calculation anchored to user account reset schedule.
    """
    now = datetime.now(timezone.utc)
    if not account_info:
        account_info = get_active_account()

    account_id = account_info.get("account", "default_user")

    # 1. Attempt Live Language Server Quota Query
    live_quota = fetch_live_antigravity_quota()
    if live_quota and live_quota.get("groups"):
        groups = []
        gemini_weekly = None
        gemini_5h = None

        for g in live_quota["groups"]:
            g_name = g.get("displayName", "Models")
            buckets_data = {}
            for b in g.get("buckets", []):
                bid = b.get("bucketId", "")
                rem_frac = b.get("remainingFraction", 1.0)
                rem_pct = round(rem_frac * 100, 1)
                used_pct = round(max(0.0, (1.0 - rem_frac) * 100), 1)
                res_time = b.get("resetTime")
                res_str = format_reset_countdown(res_time, now, rem_frac)

                b_info = {
                    "bucket_id": bid,
                    "display_name": b.get("displayName", ""),
                    "description": b.get("description", ""),
                    "remaining_fraction": rem_frac,
                    "remaining_pct": rem_pct,
                    "utilization_pct": used_pct,
                    "reset_time": res_time,
                    "resets_str": res_str
                }
                if b.get("window") == "weekly" or "weekly" in bid.lower():
                    buckets_data["weekly"] = b_info
                elif b.get("window") == "5h" or "5h" in bid.lower() or "five" in bid.lower():
                    buckets_data["five_hour"] = b_info

            g_entry = {
                "name": g_name,
                "description": g.get("description", ""),
                "weekly": buckets_data.get("weekly"),
                "five_hour": buckets_data.get("five_hour")
            }
            groups.append(g_entry)

            if "gemini" in g_name.lower():
                gemini_weekly = buckets_data.get("weekly")
                gemini_5h = buckets_data.get("five_hour")

        primary_weekly = gemini_weekly or (groups[0]["weekly"] if groups and groups[0].get("weekly") else {})
        primary_5h = gemini_5h or (groups[0]["five_hour"] if groups and groups[0].get("five_hour") else {})

        return {
            "mode": "live_service",
            "source": "language_server_live",
            "account": account_id,
            "groups": groups,
            "weekly": primary_weekly,
            "five_hour": primary_5h
        }

    # 2. Offline Fallback Calculation (when language server is unavailable)
    brain_root = get_brain_root()
    five_hours_ago = now - timedelta(hours=5)

    schedule = resolve_account_reset_schedule(account_id, pricing_config, cli_day, cli_time)
    next_reset, last_reset, weekly_reset_str = compute_account_weekly_window(
        schedule["reset_day"], schedule["reset_time_utc"], now
    )

    rl_cfg = pricing_config.get("rate_limits", {})
    weekly_limit = rl_cfg.get("weekly_token_limit", 500000000)
    five_hour_limit = rl_cfg.get("five_hour_token_limit", 50000000)

    tokens_5h = 0
    tokens_weekly = 0
    oldest_turn_5h = None

    transcripts = glob.glob(os.path.join(brain_root, "*", ".system_generated", "logs", "transcript_full.jsonl"))

    for t_path in transcripts:
        t_mtime = os.path.getmtime(t_path)
        # Scan transcripts updated within past 8 days to cover full 7-day weekly reset cycle
        if (time.time() - t_mtime) > 8 * 86400:
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
            for t_item in sdata.get("turns_summary", []):
                t_dt = parse_timestamp_iso(t_item["ts"])
                tok = t_item.get("tokens", 0)
                if t_dt >= last_reset:
                    tokens_weekly += tok
                if t_dt >= five_hours_ago:
                    tokens_5h += tok
                    if oldest_turn_5h is None or t_dt < oldest_turn_5h:
                        oldest_turn_5h = t_dt
        except Exception:
            continue

    if tokens_5h > 0 and oldest_turn_5h:
        reset_time = oldest_turn_5h + timedelta(hours=5)
        delta_5h = reset_time - now
        secs = max(0, int(delta_5h.total_seconds()))
        h_5h = secs // 3600
        m_5h = round((secs % 3600) / 60)
        if m_5h >= 60:
            h_5h += 1
            m_5h = 0
        if h_5h > 0:
            five_hour_reset_str = f"in {h_5h}h {m_5h}m"
        else:
            five_hour_reset_str = f"in {m_5h}m"
    else:
        five_hour_reset_str = "idle"

    weekly_pct = round((tokens_weekly / weekly_limit) * 100, 1) if weekly_limit > 0 else 0.0
    five_hour_pct = round((tokens_5h / five_hour_limit) * 100, 1) if five_hour_limit > 0 else 0.0

    return {
        "mode": "estimated_offline",
        "account": account_id,
        "reset_schedule": {
            "reset_day": schedule["reset_day"],
            "reset_time_utc": schedule["reset_time_utc"],
            "is_custom": schedule["is_custom"],
            "source": schedule["source"],
            "next_reset_utc": next_reset.isoformat(),
            "last_reset_utc": last_reset.isoformat()
        },
        "weekly": {
            "used_tokens": tokens_weekly,
            "limit_tokens": weekly_limit,
            "utilization_pct": weekly_pct,
            "remaining_pct": max(0.0, round(100.0 - weekly_pct, 1)),
            "resets_str": weekly_reset_str
        },
        "five_hour": {
            "used_tokens": tokens_5h,
            "limit_tokens": five_hour_limit,
            "utilization_pct": five_hour_pct,
            "remaining_pct": max(0.0, round(100.0 - five_hour_pct, 1)),
            "resets_str": five_hour_reset_str
        }
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
    acc = data.get("account")
    if acc:
        acc_str = acc.get("account") if isinstance(acc, dict) else str(acc)
        add_pair("Active Account:", acc_str)
    if cid:
        cid_display = cid if len(cid) <= 36 else cid[:33] + "..."
        add_pair("Target Session:", cid_display)
    add_pair("Active Model:", f"{model_name}")

    prov = data["provenance"]
    prov_str = f"{prov['mode'].upper()} ({prov['reported_turns']} reported, {prov['estimated_turns']} estimated)"
    add_pair("Provenance:", prov_str)

    lines.append(mid_border)

    # Rate Limits Section: Weekly limit first, 5-Hour limit directly under it
    rl = data.get("rate_limits")
    if rl:
        if rl.get("groups"):
            add_row(f"{ANSI_BOLD}Rate Limits & Quotas (Antigravity Service):{ANSI_RESET}")
            for idx, g in enumerate(rl["groups"]):
                if idx > 0:
                    add_row("")
                add_row(f"{ANSI_BOLD}[{g['name']}]{ANSI_RESET}")
                w_bucket = g.get("weekly")
                if w_bucket:
                    rem_pct = int(round(w_bucket.get("remaining_pct", 100.0)))
                    used_pct = 100 - rem_pct
                    filled = min(16, int((rem_pct / 100.0) * 16))
                    bar = "█" * filled + "░" * (16 - filled)
                    cd_str = f" (resets {w_bucket['resets_str']})" if w_bucket.get('resets_str') != "idle" else ""
                    add_row(f"  Weekly Limit Remaining{cd_str}:")
                    add_pair(f"  [{bar}]", f"{rem_pct}% ({used_pct}% used)")

                f_bucket = g.get("five_hour")
                if f_bucket:
                    rem_pct = int(round(f_bucket.get("remaining_pct", 100.0)))
                    used_pct = 100 - rem_pct
                    filled = min(16, int((rem_pct / 100.0) * 16))
                    bar = "█" * filled + "░" * (16 - filled)
                    cd_str = f" (resets {f_bucket['resets_str']})" if f_bucket.get('resets_str') != "idle" else ""
                    add_row(f"  Five Hour Limit Remaining{cd_str}:")
                    if rem_pct >= 100 and f_bucket.get('resets_str') == "idle":
                        add_pair(f"  [{bar}]", "100%")
                    else:
                        add_pair(f"  [{bar}]", f"{rem_pct}% ({used_pct}% used)")
        else:
            add_row(f"{ANSI_BOLD}Rate Limits & Quotas:{ANSI_RESET}")

            def fmt_short(n: int) -> str:
                if n >= 1_000_000_000:
                    return f"{n/1e9:.1f}B"
                if n >= 1_000_000:
                    return f"{n/1e6:.1f}M"
                if n >= 1_000:
                    return f"{n/1e3:.1f}k"
                return str(n)

            # 1. Weekly Limit
            w_data = rl["weekly"]
            w_pct = w_data.get("utilization_pct", 0.0)
            w_filled = min(16, int((min(100.0, w_pct) / 100.0) * 16))
            w_bar = "█" * w_filled + "░" * (16 - w_filled)
            u_tokens = w_data.get('used_tokens', 0)
            l_tokens = w_data.get('limit_tokens', 1000000)
            add_row(f"Weekly Limit (resets {w_data.get('resets_str', 'unknown')}):")
            add_pair(f"[{w_bar}]", f"{w_pct:.1f}% ({fmt_short(u_tokens)}/{fmt_short(l_tokens)} tokens)")

            # 2. 5-Hour Limit directly under Weekly Limit
            f_data = rl["five_hour"]
            f_pct = f_data.get("utilization_pct", 0.0)
            f_filled = min(16, int((min(100.0, f_pct) / 100.0) * 16))
            f_bar = "█" * f_filled + "░" * (16 - f_filled)
            u_tokens_f = f_data.get('used_tokens', 0)
            l_tokens_f = f_data.get('limit_tokens', 1000000)
            add_row(f"5-Hour Limit (resets {f_data.get('resets_str', 'unknown')}):")
            add_pair(f"[{f_bar}]", f"{f_pct:.1f}% ({fmt_short(u_tokens_f)}/{fmt_short(l_tokens_f)} tokens)")

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
        if rl and rl.get("mode") == "live_service":
            add_row(f"{ANSI_DIM}*Inferred cache rate. Quota synced via Antigravity.{ANSI_RESET}")
        else:
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
    parser.add_argument("--account", type=str, help="Active user account email or ID")
    parser.add_argument("--reset-day", type=str, help="Weekly limit reset day (e.g. Mon, Tue, Wed...)")
    parser.add_argument("--reset-time", type=str, help="Weekly limit reset time UTC (e.g. 18:00)")
    parser.add_argument("--save-reset", action="store_true", help="Save the reset schedule to ~/.gemini/account_resets.json for the active account")
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

    account_info = get_active_account(args.account)
    if args.save_reset:
        day = normalize_reset_day(args.reset_day) if args.reset_day else "Sun"
        t_utc = normalize_reset_time(args.reset_time) if args.reset_time else "00:00"
        saved = save_user_account_reset(account_info["account"], day, t_utc)
        if not args.json:
            if saved:
                print(f"{ANSI_GREEN}Saved reset schedule for {account_info['account']}: {day} {t_utc} UTC{ANSI_RESET}")
            else:
                print(f"{ANSI_RED}Failed to save reset schedule for {account_info['account']}{ANSI_RESET}", file=sys.stderr)

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

    if not suppress_daily:
        rate_limits = compute_rate_limits(
            pricing_config=pricing_config,
            engine_hash=engine_hash,
            account_info=account_info,
            cli_day=args.reset_day,
            cli_time=args.reset_time
        )
    else:
        rate_limits = None

    session_data["daily_totals"] = daily_totals
    session_data["rate_limits"] = rate_limits
    session_data["account"] = account_info

    payload = {
        "schema_version": SCHEMA_VERSION,
        "account": account_info,
        "conversation_id": cid or "isolated_transcript",
        "model": session_data["model"],
        "provenance": session_data["provenance"],
        "context_window": session_data["context_window"],
        "rate_limits": rate_limits,
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
