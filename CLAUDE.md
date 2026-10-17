# my-skills

Public repo (github.com/Arluigi/my-skills) of agent skills. One folder per skill: `SKILL.md` (agent-facing), `README.md` (human-facing), scripts beside them. Skills are symlinked into `~/.claude/skills` and `~/.codex/skills` from here, so edits are live.

- Add a new skill: new folder plus a row in the root README table.
- Public repo: no personal paths, emails or tokens.
- herdr-delegate: install/relink with `herdr-delegate/install.sh`; sanity check with `herdr-delegate/scripts/delegate usage` and `tiers`.

## Session Log
### 2026-10-17
- Completed: Created this public repo (github.com/Arluigi/my-skills) as the home for all skills, starting with herdr-delegate. It includes:
  - the delegate CLI;
  - leaf-only helpers that run lean, with claude-mem, superpowers and similar plugins turned off;
  - a usage-aware Claude/GPT balancer, where GPT gets a steady target share of helpers (35% base, 20–75%) and only a critical quota is a hard switch;
  - the herdr tree plugin `herdr-delegate.tree`, a `prefix+a` popup, and a tab-bar quota readout;
  - a statusline hook and `install.sh`.
  Switched commit email to the GitHub noreply address, both for this repo (history rewritten) and globally.
- Next: run it on a real multi-chunk task and tune `GPT_BASE` and the tiers from experience. Watch whether the braille-blank padding renders cleanly for other people. Optional: block pushes that expose the email in GitHub settings, and scrub Gmail from older repos.
