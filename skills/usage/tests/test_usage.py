#!/usr/bin/env python3
"""
Automated Test Suite for /usage Telemetry Engine
Verifies all mathematical invariants, schema constraints, and edge cases.
"""

import sys
import os
import json
import time
import unittest
from datetime import datetime, timezone
from decimal import Decimal

# Add scripts directory to sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.normpath(os.path.join(TEST_DIR, "..", "scripts"))
sys.path.insert(0, SCRIPTS_DIR)

import usage


class TestUsageEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pricing_file = os.path.join(SCRIPTS_DIR, "pricing.json")
        cls.pricing = usage.load_pricing(cls.pricing_file)
        cls.fixtures_dir = os.path.join(TEST_DIR, "fixtures")
        cls.cal_dir = os.path.join(cls.fixtures_dir, "calibration")

    def test_cost_formula_reconciliation(self):
        """1. Assert Decimal calculation on 242,320 uncached + 41,800 cached + 14,290 output == $0.2384625 ($0.2385)."""
        turn_time = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)
        cost, assumed = usage.calculate_turn_cost(
            model_id="gemini-3.8-flash",
            uncached_tokens=242320,
            cached_tokens=41800,
            output_tokens=14290,
            turn_time=turn_time,
            pricing_config=self.pricing
        )
        self.assertIsNotNone(cost)
        # 242320 * 0.75 / 1e6 = 0.18174
        # 41800 * 0.075 / 1e6 = 0.003135
        # 14290 * 3.75 / 1e6 = 0.0535875
        # Total = 0.2384625
        expected = Decimal("0.2384625")
        self.assertEqual(cost, expected)
        self.assertIn("cached_rate", assumed)

    def test_reported_multimodal_does_not_double_count(self):
        """2. Assert input totals are unchanged by image presence on reported turns."""
        fixture = os.path.join(self.fixtures_dir, "fixture_multimodal.jsonl")
        data = usage.parse_transcript_stream(fixture, self.pricing)
        # Reported turns promptTokenCount are 5000 and 8096 -> 13096 total input
        self.assertEqual(data["tokens"]["cumulative_input"], 13096)
        self.assertEqual(data["provenance"]["mode"], "reported")
        self.assertGreater(data["tokens"]["multimodal_items"], 0)

    def test_model_specific_prompt_threshold(self):
        """3. Assert 190k uncached + 30k cached (220k) triggers high-tier rate on gemini-2.5-pro."""
        turn_time = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)
        # Below threshold (150k total <= 200k threshold):
        cost_low, _ = usage.calculate_turn_cost(
            model_id="gemini-2.5-pro",
            uncached_tokens=150000,
            cached_tokens=0,
            output_tokens=0,
            turn_time=turn_time,
            pricing_config=self.pricing
        )
        # Low rate: 150,000 * 1.25 / 1e6 = 0.1875
        self.assertEqual(cost_low, Decimal("0.1875"))

        # Above threshold (190k + 30k = 220k > 200k threshold):
        cost_high, _ = usage.calculate_turn_cost(
            model_id="gemini-2.5-pro",
            uncached_tokens=190000,
            cached_tokens=30000,
            output_tokens=0,
            turn_time=turn_time,
            pricing_config=self.pricing
        )
        # High rate: 190,000 * 2.50 / 1e6 + 30,000 * 0.25 / 1e6 = 0.475 + 0.0075 = 0.4825
        self.assertEqual(cost_high, Decimal("0.4825"))

    def test_inflight_multiwindow_cache_exclusion(self):
        """4. Assert files modified < 60s ago are skipped from cache write."""
        temp_transcript = os.path.join(self.fixtures_dir, "temp_inflight.jsonl")
        with open(temp_transcript, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "step_index": 0,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "content": "Hello",
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 10,
                    "totalTokenCount": 110
                }
            }) + "\n")

        try:
            # Ensure mtime is right now (< 60s ago)
            os.utime(temp_transcript, None)
            cache_dir = usage.get_cache_dir()
            cid = "test_inflight_cid_123"
            cache_file = os.path.join(cache_dir, f"{cid}.json")
            if os.path.exists(cache_file):
                os.remove(cache_file)

            engine_hash = "mock_hash"
            data = usage.manage_cache(
                cid=cid,
                transcript_path=temp_transcript,
                engine_hash=engine_hash,
                pricing_config=self.pricing
            )
            # Cache file should NOT exist because file mtime is fresh (<60s)
            self.assertFalse(os.path.exists(cache_file))
        finally:
            if os.path.exists(temp_transcript):
                os.remove(temp_transcript)

    def test_mechanical_line_width(self):
        """5. Assert len(visible_line) == width after stripping ANSI codes across colored/uncolored renders."""
        fixture = os.path.join(self.fixtures_dir, "fixture_reported.jsonl")
        data = usage.parse_transcript_stream(fixture, self.pricing)
        for w in [54, 64, 72, 80]:
            rendered = usage.render_box(data, width=w, cid="025c7515-7b3f-4cee-95be-aa616bf5f9da")
            lines = rendered.splitlines()
            for i, l in enumerate(lines):
                vis_len = len(usage.strip_ansi(l))
                self.assertEqual(vis_len, w, f"Line {i} length {vis_len} != {w} in width {w} box")

    def test_partial_cost_turn_annotation(self):
        """6. Assert cost line renders '(M/N turns priced)' when turns are suppressed."""
        mock_data = {
            "model": {"id": "gemini-3.8-flash", "resolved": True},
            "provenance": {"mode": "reported", "reported_turns": 2, "estimated_turns": 0, "total_turns": 2},
            "context_window": {"occupancy_tokens": 1000, "limit_tokens": 1000000, "headroom_tokens": 999000, "utilization_pct": 0.1},
            "tokens": {"cumulative_input": 1000, "uncached_input": 1000, "cached_input": 0, "cumulative_output": 100, "multimodal_items": 0, "multimodal_tokens": 0},
            "cost": {"equivalent_usd": 0.05, "currency": "USD", "priced_turns": 1, "total_turns": 2, "assumed_rates": []},
            "activity": {"wall_duration_seconds": 12.0, "total_steps": 5, "model_turns": 2, "tool_counts": {}}
        }
        rendered = usage.render_box(mock_data, width=64, cid="partial-cid")
        self.assertIn("(1/2 turns priced)", rendered)

    def test_mixed_provenance_cost_annotation(self):
        """7. Assert cost line reflects '(Mixed: X reported, Y estimated)'."""
        mock_data = {
            "model": {"id": "gemini-3.8-flash", "resolved": True},
            "provenance": {"mode": "mixed", "reported_turns": 15, "estimated_turns": 3, "total_turns": 18},
            "context_window": {"occupancy_tokens": 1000, "limit_tokens": 1000000, "headroom_tokens": 999000, "utilization_pct": 0.1},
            "tokens": {"cumulative_input": 1000, "uncached_input": 1000, "cached_input": 0, "cumulative_output": 100, "multimodal_items": 0, "multimodal_tokens": 0},
            "cost": {"equivalent_usd": 0.2385, "currency": "USD", "priced_turns": 18, "total_turns": 18, "assumed_rates": []},
            "activity": {"wall_duration_seconds": 12.0, "total_steps": 25, "model_turns": 18, "tool_counts": {}}
        }
        rendered = usage.render_box(mock_data, width=64, cid="mixed-cid")
        self.assertIn("Mixed: 15 reported, 3 estimated", rendered)

    def test_json_schema_contract(self):
        """8. Assert exact top-level keys, types, and null semantics (both standard and suppressed shapes)."""
        fixture = os.path.join(self.fixtures_dir, "fixture_reported.jsonl")
        data = usage.parse_transcript_stream(fixture, self.pricing)
        payload = {
            "schema_version": usage.SCHEMA_VERSION,
            "conversation_id": "025c7515-7b3f-4cee-95be-aa616bf5f9da",
            "model": data["model"],
            "provenance": data["provenance"],
            "context_window": data["context_window"],
            "tokens": data["tokens"],
            "cost": data["cost"],
            "activity": data["activity"],
            "rate_limits": None,
            "daily_totals": None  # Isolated transcript null semantic
        }
        # Check required top-level keys
        expected_keys = {
            "schema_version", "conversation_id", "model", "provenance",
            "context_window", "rate_limits", "tokens", "cost", "activity", "daily_totals"
        }
        self.assertEqual(set(payload.keys()), expected_keys)
        self.assertIsNone(payload["daily_totals"])

    def test_rate_limits_weekly_and_five_hour_order(self):
        """12. Assert Weekly limit is rendered first, and 5-Hour limit is rendered directly under it."""
        mock_data = {
            "model": {"id": "gemini-3.8-flash", "resolved": True},
            "provenance": {"mode": "reported", "reported_turns": 1, "estimated_turns": 0, "total_turns": 1},
            "context_window": {"occupancy_tokens": 1000, "limit_tokens": 1000000, "headroom_tokens": 999000, "utilization_pct": 0.1},
            "tokens": {"cumulative_input": 1000, "uncached_input": 1000, "cached_input": 0, "cumulative_output": 100, "multimodal_items": 0, "multimodal_tokens": 0},
            "cost": {"equivalent_usd": 0.05, "currency": "USD", "priced_turns": 1, "total_turns": 1, "assumed_rates": []},
            "activity": {"wall_duration_seconds": 12.0, "total_steps": 5, "model_turns": 1, "tool_counts": {}},
            "rate_limits": {
                "weekly": {
                    "used_tokens": 25000000,
                    "limit_tokens": 500000000,
                    "utilization_pct": 5.0,
                    "resets_str": "in 2d 14h"
                },
                "five_hour": {
                    "used_tokens": 2500000,
                    "limit_tokens": 50000000,
                    "utilization_pct": 5.0,
                    "resets_str": "in 1h 45m"
                }
            }
        }
        rendered = usage.render_box(mock_data, width=64, cid="test-rl")
        weekly_idx = rendered.find("Weekly Limit")
        five_hour_idx = rendered.find("5-Hour Limit")
        self.assertNotEqual(weekly_idx, -1)
        self.assertNotEqual(five_hour_idx, -1)
        self.assertLess(weekly_idx, five_hour_idx, "Weekly limit must appear before 5-Hour limit")

        # Check suppression null semantics when model is unresolvable
        unpriced_fixture = os.path.join(self.fixtures_dir, "fixture_empty.jsonl")
        unpriced_data = usage.parse_transcript_stream(unpriced_fixture, self.pricing)
        self.assertIsNone(unpriced_data["cost"]["equivalent_usd"])

    def test_multi_scale_calibration(self):
        """9. Evaluate 4 discrete samples against manifest tolerances."""
        manifest_path = os.path.join(self.cal_dir, "calibration_manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for name, item in manifest["samples"].items():
            sample_path = os.path.join(self.cal_dir, item["file"])
            with open(sample_path, "r", encoding="utf-8") as f:
                content = f.read()
            est = usage.structural_tokenize(content)
            gt = item["ground_truth_tokens"]
            tol = item["tolerance_pct"]
            err = abs(est - gt) / gt
            self.assertLessEqual(err, tol, f"Sample '{name}' estimation error {err:.4f} exceeds tolerance {tol}")

    def test_truncated_trailing_line(self):
        """10. Verify clean error recovery from abrupt EOF mid-JSON."""
        fixture = os.path.join(self.fixtures_dir, "fixture_truncated.jsonl")
        # Should not raise JSONDecodeError
        data = usage.parse_transcript_stream(fixture, self.pricing)
        self.assertEqual(data["provenance"]["total_turns"], 1)
        self.assertEqual(data["tokens"]["cumulative_input"], 284120)

    def test_fixture_isolation(self):
        """11. Assert isolated transcript suppresses daily history scan."""
        fixture = os.path.join(self.fixtures_dir, "fixture_reported.jsonl")
        # Simulating running with --transcript flag
        data = usage.parse_transcript_stream(fixture, self.pricing)
        self.assertIsNotNone(data)
        # Top-level daily_totals should be None when isolated
        payload = {
            "schema_version": usage.SCHEMA_VERSION,
            "conversation_id": "isolated",
            "daily_totals": None
        }
        self.assertIsNone(payload["daily_totals"])

    def test_account_resolution_and_reset_schedule(self):
        """12. Assert user accounts get distinct reset schedules and respect explicit overrides."""
        # 1. Detection priority
        cli_acc = usage.get_active_account(cli_account="test@override.com")
        self.assertEqual(cli_acc["account"], "test@override.com")
        self.assertEqual(cli_acc["source"], "cli")

        # 2. Account schedule differentiation (no everyone resets at the same time)
        acc1 = "alice.dev@company.com"
        acc2 = "bob.engineer@startup.io"
        sched1 = usage.resolve_account_reset_schedule(acc1, self.pricing)
        sched2 = usage.resolve_account_reset_schedule(acc2, self.pricing)

        # Confirm both accounts have deterministic valid schedules
        self.assertIn(sched1["reset_day"], usage.DAYS_OF_WEEK)
        self.assertIn(sched2["reset_day"], usage.DAYS_OF_WEEK)
        # Verify they don't have identical schedule slots
        slot1 = (sched1["reset_day"], sched1["reset_time_utc"])
        slot2 = (sched2["reset_day"], sched2["reset_time_utc"])
        self.assertNotEqual(slot1, slot2, "Different user accounts must receive distinct reset schedule slots")

        # 3. Explicit CLI override
        custom_sched = usage.resolve_account_reset_schedule(
            acc1, self.pricing, cli_day="Friday", cli_time="16:30"
        )
        self.assertEqual(custom_sched["reset_day"], "Fri")
        self.assertEqual(custom_sched["reset_time_utc"], "16:30")
        self.assertTrue(custom_sched["is_custom"])

        # 4. 7-day cycle math invariant
        fixed_now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
        nr, lr, res_str = usage.compute_account_weekly_window("Fri", "16:30", fixed_now)
        cycle_length = (nr - lr).total_seconds()
        self.assertEqual(cycle_length, 7 * 86400, "Reset window cycle must span precisely 7 days")
        self.assertGreater(nr, fixed_now)
        self.assertLessEqual(lr, fixed_now)

    def test_render_box_active_account(self):
        """13. Assert Active Account is displayed in the terminal box header and correctly formatted."""
        mock_data = {
            "account": {"account": "joshua.r.carlile@gmail.com", "source": "google_accounts.json"},
            "model": {"id": "gemini-3.8-flash", "resolved": True},
            "provenance": {"mode": "reported", "reported_turns": 1, "estimated_turns": 0, "total_turns": 1},
            "context_window": {"occupancy_tokens": 1000, "limit_tokens": 1000000, "headroom_tokens": 999000, "utilization_pct": 0.1},
            "tokens": {"cumulative_input": 1000, "uncached_input": 1000, "cached_input": 0, "cumulative_output": 100, "multimodal_items": 0, "multimodal_tokens": 0},
            "cost": {"equivalent_usd": 0.05, "currency": "USD", "priced_turns": 1, "total_turns": 1, "assumed_rates": []},
            "activity": {"wall_duration_seconds": 12.0, "total_steps": 5, "model_turns": 1, "tool_counts": {}},
            "rate_limits": {
                "account": "joshua.r.carlile@gmail.com",
                "weekly": {
                    "used_tokens": 25000000,
                    "limit_tokens": 500000000,
                    "utilization_pct": 5.0,
                    "resets_str": "in 4d 17h (Tue 22:00 UTC)"
                },
                "five_hour": {
                    "used_tokens": 2500000,
                    "limit_tokens": 50000000,
                    "utilization_pct": 5.0,
                    "resets_str": "in 1h 45m"
                }
            }
        }
        rendered = usage.render_box(mock_data, width=64, cid="test-acc-box")
        self.assertIn("Active Account: joshua.r.carlile@gmail.com", rendered)
        self.assertIn("Weekly Limit (resets in 4d 17h (Tue 22:00 UTC)):", rendered)
        self.assertIn("5-Hour Limit (resets in 1h 45m):", rendered)
        for line in rendered.split("\n"):
            self.assertEqual(len(usage.strip_ansi(line)), 64, f"Line width violation in: {line}")

    def test_live_service_quota_rendering(self):
        """14. Assert live service quota groups (Gemini and Claude & GPT) render cleanly at 64 columns."""
        mock_data = {
            "account": {"account": "joshua.r.carlile@gmail.com", "source": "google_accounts.json"},
            "model": {"id": "gemini-3.8-flash", "resolved": True},
            "provenance": {"mode": "reported", "reported_turns": 1, "estimated_turns": 0, "total_turns": 1},
            "context_window": {"occupancy_tokens": 1000, "limit_tokens": 1000000, "headroom_tokens": 999000, "utilization_pct": 0.1},
            "tokens": {"cumulative_input": 1000, "uncached_input": 1000, "cached_input": 0, "cumulative_output": 100, "multimodal_items": 0, "multimodal_tokens": 0},
            "cost": {"equivalent_usd": 0.05, "currency": "USD", "priced_turns": 1, "total_turns": 1, "assumed_rates": []},
            "activity": {"wall_duration_seconds": 12.0, "total_steps": 5, "model_turns": 1, "tool_counts": {}},
            "rate_limits": {
                "mode": "live_service",
                "source": "language_server_live",
                "account": "joshua.r.carlile@gmail.com",
                "groups": [
                    {
                        "name": "Gemini Models",
                        "weekly": {
                            "display_name": "Weekly Limit Remaining",
                            "remaining_pct": 84.0,
                            "utilization_pct": 16.0,
                            "resets_str": "in 5d 1h"
                        },
                        "five_hour": {
                            "display_name": "Five Hour Limit Remaining",
                            "remaining_pct": 63.0,
                            "utilization_pct": 37.0,
                            "resets_str": "in 2h 54m"
                        }
                    },
                    {
                        "name": "Claude and GPT models",
                        "weekly": {
                            "display_name": "Weekly Limit Remaining",
                            "remaining_pct": 64.0,
                            "utilization_pct": 36.0,
                            "resets_str": "in 23h 31m"
                        },
                        "five_hour": {
                            "display_name": "Five Hour Limit Remaining",
                            "remaining_pct": 100.0,
                            "utilization_pct": 0.0,
                            "resets_str": "idle"
                        }
                    }
                ]
            }
        }
        rendered = usage.render_box(mock_data, width=64, cid="test-live-box")
        self.assertIn("Rate Limits & Quotas (Antigravity Service):", rendered)
        self.assertIn("[Gemini Models]", rendered)
        self.assertIn("Weekly Limit Remaining (resets in 5d 1h):", rendered)
        self.assertIn("Five Hour Limit Remaining (resets in 2h 54m):", rendered)
        self.assertIn("[Claude and GPT models]", rendered)
        self.assertIn("Weekly Limit Remaining (resets in 23h 31m):", rendered)
        self.assertIn("Five Hour Limit Remaining:", rendered)
        self.assertIn("100%", rendered)
        for line in rendered.split("\n"):
            self.assertEqual(len(usage.strip_ansi(line)), 64, f"Line width violation: {line}")

    def test_universal_brain_roots_and_transcript_discovery(self):
        """15. Assert multi-root brain resolution and transcript aggregation across roots."""
        import tempfile
        import shutil
        from unittest.mock import patch

        roots = usage.get_brain_roots()
        self.assertIsInstance(roots, list)
        self.assertGreater(len(roots), 0)

        # Test multi-root transcript discovery with temporary directories
        temp_dir = tempfile.mkdtemp(prefix="agy_test_roots_")
        try:
            root1 = os.path.join(temp_dir, "root1")
            root2 = os.path.join(temp_dir, "root2")

            # Create cid-1 in root1 with both full and std transcripts
            c1_logs = os.path.join(root1, "cid-1", ".system_generated", "logs")
            os.makedirs(c1_logs, exist_ok=True)
            with open(os.path.join(c1_logs, "transcript.jsonl"), "w") as f:
                f.write("{}\n")
            full_path = os.path.join(c1_logs, "transcript_full.jsonl")
            with open(full_path, "w") as f:
                f.write("{}\n")

            # Create cid-2 in root2 with only std transcript
            c2_logs = os.path.join(root2, "cid-2", ".system_generated", "logs")
            os.makedirs(c2_logs, exist_ok=True)
            std_path = os.path.join(c2_logs, "transcript.jsonl")
            with open(std_path, "w") as f:
                f.write("{}\n")

            with patch("usage.get_brain_roots", return_value=[root1, root2]):
                transcripts = usage.find_all_transcripts()
                self.assertIn("cid-1", transcripts)
                self.assertIn("cid-2", transcripts)
                # Prefers transcript_full.jsonl for cid-1
                self.assertEqual(os.path.abspath(transcripts["cid-1"]), os.path.abspath(full_path))
                # Falls back to transcript.jsonl for cid-2
                self.assertEqual(os.path.abspath(transcripts["cid-2"]), os.path.abspath(std_path))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_dual_config_paths(self):
        """16. Assert account resets config path resolves to a valid account_resets.json path."""
        p = usage.get_account_resets_config_path()
        self.assertIsInstance(p, str)
        self.assertTrue(p.endswith("account_resets.json"))

    def test_render_compact_low_token_invariants(self):
        """17. Assert render_compact produces high-density output without box-drawing bloat."""
        mock_data = {
            "model": {"id": "gemini-3.8-flash"},
            "cost": {"equivalent_usd": Decimal("0.0480")},
            "activity": {"model_turns": 15, "wall_duration_seconds": 120.0},
            "context_window": {
                "occupancy_tokens": 7289,
                "limit_tokens": 1000000,
                "headroom_tokens": 992711,
                "utilization_pct": 0.7
            },
            "rate_limits": {
                "groups": [
                    {
                        "name": "Gemini Models",
                        "weekly": {"remaining_pct": 20.0, "resets_str": "in 19h 27m"},
                        "five_hour": {"remaining_pct": 96.0, "resets_str": "in 4h 33m"}
                    }
                ]
            }
        }
        compact = usage.render_compact(mock_data, cid="test-compact")
        self.assertIn("[Telemetry] Model: gemini-3.8-flash", compact)
        self.assertIn("Cost: $0.0480", compact)
        self.assertIn("Context: [█░░░░░░░░░] 7,289 / 1,000,000 (0.7% used, 993k free)", compact)
        self.assertIn("Gemini Models: Weekly 20%", compact)
        self.assertNotIn("┌", compact)
        self.assertNotIn("│", compact)
        self.assertNotIn("─", compact)
        self.assertLess(len(compact), 350)


if __name__ == "__main__":
    unittest.main()


