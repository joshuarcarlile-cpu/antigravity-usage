# Antigravity `/usage` Telemetry Engine — Project Standards

## 1. Local Operating & Plan-First Standards
- **Gate 0 (Plan-First)**: Before modifying files, adding dependencies, or running mutating commands, produce an implementation plan and await explicit user approval.
- **Canonical Source of Truth**: This repository (`C:\Users\joshu\Projects\Antigravity usage project`) is the single source of truth for the `/usage` engine.
- **Runtime Deployment**: Production runtime assets reside at `~/.gemini/config/skills/usage/` (linked via `-Dev` junction for active development) and `~/.gemini/antigravity-ide/bin/`. Deployments must never leave loose files in user roots.
- **Scope Discipline**: Confine modifications strictly to task scope; report adjacent findings under `NOTICED BUT NOT TOUCHING`.

## 2. Telemetry Engine Invariants
- **Exact Decimal Arithmetic**: All token price and cost calculations MUST use `decimal.Decimal` with explicit quantizing (`ROUND_HALF_UP`). Zero floating-point math is permitted in financial calculations.
- **Dual-Path Integrity**: Maintain support for both official IDE `usageMetadata` and calibrated token estimation fallback. Never break either path.
- **Zero-Inline & Path Safety**: In PowerShell scripts, never run inline code one-liners; always use `-LiteralPath` instead of `-Path` for filesystem operations.
- **PowerShell 5.1 Backward Compatibility**: Never use PowerShell 7+ operators (`??`, `?:`); all `.ps1` scripts must run cleanly on native Windows PowerShell 5.1.
- **Token-Efficiency Invariant**: Support `--compact` rendering mode for ultra-low token consumption (~80 tokens vs ~450 tokens standard box).
- **Self-Contained Skill Triggering**: The engine triggers automatically via `skills/usage/SKILL.md` frontmatter and Global Rule §5. Do NOT create duplicate standalone rule files.

## 3. Verification & Testing Hard Gate
- Before committing or concluding any turn, run the automated test suite:
  ```powershell
  python -m unittest discover -s skills/usage/tests -p "test_*.py" -v
  ```
- All tests must pass (exit code 0). Never claim success without test evidence.
- New features or schema changes must be accompanied by unit tests in `skills/usage/tests/`.

## 4. Compounding Self-Correction Protocol
- Circuit breaker: Halt after 2 identical failures or 4 progressive cycles.
- Persist lessons as a 1-line rule in this file (budget capped at 100 lines / 16 KB) or declare `NO ARTIFACT NEEDED`.
