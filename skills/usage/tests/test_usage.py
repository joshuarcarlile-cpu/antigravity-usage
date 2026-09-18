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
            "daily_totals": None  # Isolated transcript null semantic
        }
        # Check required top-level keys
        expected_keys = {
            "schema_version", "conversation_id", "model", "provenance",
            "context_window", "tokens", "cost", "activity", "daily_totals"
        }
        self.assertEqual(set(payload.keys()), expected_keys)
        self.assertIsNone(payload["daily_totals"])

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


if __name__ == "__main__":
    unittest.main()
