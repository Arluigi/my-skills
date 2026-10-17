---
name: herdr-delegate
description: Use when running inside Herdr (HERDR_ENV=1) and a task has self-contained chunks (implementation, tests, refactors, research sweeps, second-opinion reviews) that a cheaper or different model can do while you orchestrate and review. Spawns Claude/Codex/Gemini subagents as visible panes under your Herdr space. Applies without the user mentioning Herdr; this skill is the user's standing opt-in.
---

# Herdr delegate

You are the orchestrator: keep the plan, the judgment calls, and the final review. Hand bounded work to cheaper models running as visible Herdr panes, which show up as `↳` entries under your space in the agents sidebar.

The user has opted into this, so you don't need them to mention Herdr. The generic `herdr` skill's "only when explicitly asked" rule does not apply to this skill.

Script: `~/.claude/skills/herdr-delegate/scripts/delegate` (call it `$D`). Check `test "$HERDR_ENV" = 1` first; outside Herdr, use your native subagent tool instead.

## When to delegate

Delegate when a chunk is **self-contained, describable in one brief, and checkable**, and doing it yourself would burn heavy-model usage on routine tokens. Don't delegate when:
- the task takes under ~2 minutes for you (startup plus the brief costs more);
- it's a quick read-only lookup (use your native subagent tool with a cheap model, e.g. `model: haiku`);
- the work depends on context only you hold and can't easily write down;
- two chunks would touch the same files (run them sequentially, or give one child both).

## Routing

**Usage-aware.** Run `$D usage` before a delegation-heavy task and again every few spawns. It shows:
- Claude Code's 5-hour and 7-day quota, and Codex's 7-day quota, with weekly pace;
- your own context left;
- advice.

Act on the advice, beyond what the router does:
- **Claude tight:** delegate more, and use `review-gpt` for reviews. Keep your own Opus turns short: read reports and diffs, not whole files.
- **GPT tight:** keep work on Claude tiers.
- **Your context under 30%:** push reading and searching to `scout` helpers and ask for short reports.

Routing is automatic and gradual. You (Claude) stay the orchestrator, and GPT is always a supplement:
- **Mixed tiers alternate providers.** `scout`, `light`, `work` and `heavy` switch between their Claude and GPT equivalents to keep GPT near a target share of recent helper spawns.
- **The target moves smoothly.** It is 35% when the two quotas are even, and slides between 20% and 75% as the pressure gap moves. There's no threshold where everything flips.
- **Critical is the only hard switch.** A provider at critical (score 85 or more) hands everything to the other.
- **`-gpt` tiers stay on GPT** unless GPT is critical.
- **Pinning:** a raw `kind:model:effort` spec is never rerouted.
- **Where to change it:** `GPT_BASE`, `GPT_MIN` and `GPT_MAX` in `scripts/usage.py`.

`$D tiers` shows what each tier would pick next. Pick the cheapest tier that will plausibly succeed, and escalate on failure rather than starting high.

| Tier | Model | Use for |
|---|---|---|
| `scout` | Claude Haiku 5.5 | Read/search/summarize, inventory a codebase, collect facts, run commands and report. No design decisions. |
| `light` | Codex GPT-6 Luna (high) | Bounded mechanical edits: renames, boilerplate, fixtures, simple tests, applying a spec'd change across files. |
| `work` | Claude Sonnet 5.5 | **Default** for real implementation: features, bug fixes, test suites, refactors with a clear target. |
| `work-gpt` | Codex GPT-6.1 Sol (medium) | Same tier, spent from the ChatGPT quota. Use it to spread load or to run two implementers in parallel. |
| `heavy` | Claude Opus 5.5 (high) | Hard debugging or design you want done in parallel with your own work. Use sparingly. |
| `heavy-gpt` | Codex GPT-6.1 Sol (high) | Hard work on the OpenAI side. |
| `review-gpt` | Codex GPT-6 Astra (high) | Independent cross-provider review of a risky diff. A different model family catches different bugs. |

Also accepted: raw `kind:model[:effort]`, e.g. `codex:gpt-6-luna:medium`, `claude:sonnet:high`, `gemini:<model>`.

Why this table: vendors and third-party evals agree that Sonnet is the everyday coding default and Opus is for long-horizon judgment. Haiku and Luna are aimed at high-volume, well-scoped subtasks. Higher effort mostly adds time on routine work. Retune `tier_spec` in the script as experience accumulates.

## Workflow

1. **Plan.** Split the task into chunks with disjoint file ownership. Decide the tier for each.
2. **Brief.** The child sees only the brief. Include absolute paths, the goal, constraints ("don't touch X"), and how to verify (the exact test command). For long briefs, write them to a file and pass `--task-file`.
3. **Spawn.**
   - One chunk: `$D spawn <name> <tier> --task "..."` blocks and prints the child's report.
   - Parallel chunks: `--no-wait` for each, then `$D wait <name>` for each.
   - Use `--cwd DIR` for a different directory, and a git worktree for parallel edits in one repo.
4. **Review. This is the point of the pattern.** Don't trust the report. Read the actual diff (`git diff`) and rerun the verification yourself.
   - Small fix needed: `$D ask <name> "..."` (the child keeps its context).
   - Wrong approach: re-brief at a higher tier (`work` → `heavy`).
   - For risky changes, add a `review-gpt` pass before you sign off.
5. **Close.** `$D close <name>` or `$D close --all` closes only panes this script spawned. Close children once their work is accepted; idle panes clutter the sidebar.

Names follow `[a-z][a-z0-9_-]{0,31}` and must be unique across the Herdr server, so name them per task (e.g. `auth-tests`). `$D list` shows your children and their states.

## Exit codes and blocked children

- `0` means the report was printed.
- `3` means the child is **blocked** or stalled; its screen is printed to stderr. Usually this is a permission or approval dialog. If it's within the brief's scope and harmless, answer it with `herdr agent send-keys <name> ...`. If it's destructive or outside the scope, ask the user. Never blindly resend the prompt.
- `4` means a timeout. The child may still be working, so check `herdr agent get <name>` before acting.

Startup handles Claude's folder-trust prompt and Codex's update prompt by itself.

## Lean helpers and the sidebar tree

- **Helpers are leaves.** Child panes carry `HERDR_DELEGATE_CHILD=1`, so `spawn`/`ask`/`close` refuse to run from a helper. Claude helpers also start without the `Agent` tool, and every brief tells the helper to do the work itself.
- **Lean helpers.** Claude children launch with `--settings` that turns off claude-mem, superpowers, vercel and a few other plugins that inject context at session start (`HELPER_SETTINGS` in the script). Briefs therefore have to carry everything the child needs; it has no memory of past sessions.
- **Sidebar tree.** The `herdr-delegate.tree` Herdr plugin (`plugin/`) tags agents with display tokens and sorts the Agents panel, so children render as `├─ ● name model/effort` under their orchestrator. The script runs `plugin/tree_sync.py` after every spawn and close. If the tree looks stale, run it by hand.
- **Subagents panel.** `prefix+a` opens a popup with a live tree, elapsed time and task for every child. Press 1–9 to jump to a child.
