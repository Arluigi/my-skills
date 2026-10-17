# herdr-delegate

Let an expensive model orchestrate while cheaper ones do the routine work, all of them visible in [Herdr](https://herdr.dev).

Your main agent (say Claude Opus) splits a task, hands the self-contained pieces to helpers (Sonnet, Haiku, GPT-6.1 Sol, GPT-6 Luna, ...), and reviews what comes back. Each helper is a real interactive session in its own Herdr pane, so you can watch it, read along, or step in. In the Agents panel the helpers hang off their orchestrator like a tree:

```
~
● claude                 ← your orchestrator
├─ ● auth-tests
│      sonnet/medium
└─ ● api-review
       gpt-6-astra/high
```

It works with Claude Code and Codex as orchestrators, and with Claude, Codex and Gemini CLIs as helpers.

## What's in it

- **`SKILL.md`.** The agent-facing instructions: when to delegate, which tier to pick, and the plan → brief → spawn → review → close loop. It also says to review the actual diff rather than trust the helper's report.
- **`scripts/delegate`.** One CLI that does the plumbing:
  - opens a `subagents` tab in the caller's space and starts the agent with the right model and effort;
  - gets past startup prompts (folder trust, Codex update);
  - sends the brief, waits, and returns the helper's Markdown report.
- **`scripts/usage.py`.** Usage-aware routing. It reads Claude Code's 5-hour and 7-day limits and Codex's limits, and keeps GPT working as a steady *supplement* to Claude instead of a fallback that only kicks in once you run out.
- **`plugin/`.** A Herdr plugin (`herdr-delegate.tree`) that draws the tree in the Agents panel, plus a `prefix+a` popup listing every helper live.

## Install

Requirements: Herdr ≥ 0.9.3, `jq`, `python3`, macOS or Linux, and whichever agent CLIs you want as helpers (`claude`, `codex`, `gemini`).

```bash
git clone https://github.com/Arluigi/my-skills ~/code/my-skills
~/code/my-skills/herdr-delegate/install.sh
```

The installer symlinks the skill into `~/.claude/skills` (and `~/.codex/skills` if Codex is installed) and links the Herdr plugin. It leaves three optional steps to you, because they edit your own config:

1. **Sidebar tree, colors, popup, quota readout.** Paste [`herdr/config-snippet.toml`](herdr/config-snippet.toml) into `~/.config/herdr/config.toml`, then run `herdr server reload-config`.
2. **Claude usage data.** In your Claude Code statusline command, pipe the input JSON through the hook:
   ```bash
   input=$(cat)
   echo "$input" | ~/.claude/skills/herdr-delegate/scripts/statusline-hook.sh
   ```
   Codex usage is read from `~/.codex/sessions` automatically.
3. **Delegate without being asked.** Add a line like this to `~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`:
   > Inside Herdr (`HERDR_ENV=1`), proactively use the herdr-delegate skill when a task has self-contained chunks; orchestrate and review yourself.

   In a session that's already open, type `/herdr-delegate`.

## Using it

Agents call the script themselves; you mostly just watch. Here's what it looks like by hand:

```bash
D=~/.claude/skills/herdr-delegate/scripts/delegate
$D usage                                    # quotas, GPT target share, your context, advice
$D tiers                                    # what each tier would pick next
$D spawn auth-tests work --task-file brief.md          # blocks, prints the report
$D spawn sweep scout --no-wait --task "List every caller of parse_config"
$D wait sweep
$D ask auth-tests "Also cover the expired-token path"  # follow-up, same context
$D list
$D close --all                              # closes only panes delegate opened
```

### Tiers

| Tier | Claude side | GPT side | For |
|---|---|---|---|
| `scout` | Haiku | GPT-6 Luna | read, search, summarize |
| `light` | Haiku (high) | GPT-6 Luna (high) | mechanical edits, boilerplate, simple tests |
| `work` | Sonnet | GPT-6.1 Sol | default implementation |
| `heavy` | Opus (high) | GPT-6.1 Sol (high) | hard design or debugging, sparingly |
| `work-gpt` / `heavy-gpt` | | GPT-6.1 Sol | pinned to GPT |
| `review-gpt` | | GPT-6 Astra (high) | cross-provider review of risky diffs |

To pin an exact model, pass `kind:model[:effort]` (e.g. `claude:sonnet:high`, `gemini:<model>`).

### How usage-aware routing works

- **Mixed tiers alternate.** `scout`, `light`, `work` and `heavy` switch between their Claude and GPT versions. The goal is to keep GPT at a target share of recent helper spawns.
- **The target moves gradually.** It's 35% when both quotas are even, and slides between 20% and 75% as one provider gets used more than the other. There's no threshold where everything flips.
- **Weekly pace counts.** A weekly window is scored by how fast you're using it as well as by percent used. Pace counts for more as the week goes on, so one heavy evening early in the week doesn't skew it.
- **Only critical is a hard switch.** A provider at critical (score ≥ 85) hands every tier to the other provider.
- **Tuning:** change `GPT_BASE`, `GPT_MIN` and `GPT_MAX` in `scripts/usage.py`.

### Helpers are lean leaves

- **Fewer plugins.** Claude helpers start with context-heavy plugins turned off (memory plugins, workflow plugins), so a small handoff doesn't pay ~20k tokens of startup context. Override this with `HERDR_DELEGATE_HELPER_SETTINGS`, a JSON object passed to `claude --settings`.
- **No delegating.** Helpers can't delegate further: their panes carry `HERDR_DELEGATE_CHILD=1`, the script refuses to spawn from them, and Claude helpers start without the `Agent` tool.

## Limits

- **The tree is a projection, not a real hierarchy.** Herdr has no parent/child relation between agents. The tree comes from display-only pane metadata plus an `agent.view.set` sort. Herdr's plugin v1 can't draw new native panels, so the "subagents panel" is a popup.
- **Startup takes time.** Each helper is a full interactive session and takes 10–30 seconds to start. For quick lookups, use your agent's built-in subagents.
- **Model names date.** They're current as of October 2026; edit `MIXED`/`PINNED` in `scripts/usage.py` as they change.
- **Codex usage can lag.** Codex usage only updates while a Codex session is running. Readings older than 6 hours are shown but not used for routing.
