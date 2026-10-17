# my-skills

Public repo (github.com/Arluigi/my-skills) of agent skills. One folder per skill: `SKILL.md` (agent-facing), `README.md` (human-facing), scripts beside them. Skills are symlinked into `~/.claude/skills` and `~/.codex/skills` from here, so edits are live.

- Add a new skill: new folder plus a row in the root README table.
- Public repo: no personal paths, emails or tokens.
- herdr-delegate: install/relink with `herdr-delegate/install.sh`; sanity check with `herdr-delegate/scripts/delegate usage` and `tiers`.

## Session Log
### 2026-10-17
- Completed: created repo with herdr-delegate (delegate CLI, usage-aware Claude/GPT balancer, herdr tree plugin + prefix+a popup, statusline hook, installer).
- Next: try it on a real multi-chunk task; tune GPT_BASE once the share feels off.
