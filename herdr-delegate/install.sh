#!/usr/bin/env bash
# Install herdr-delegate: link the skill into Claude Code (and Codex, if
# present), register the Herdr plugin, and print the remaining manual steps.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }

echo "herdr-delegate install"
for dep in herdr jq python3; do
  command -v "$dep" >/dev/null || { echo "missing dependency: $dep" >&2; exit 1; }
done
ok "dependencies: herdr jq python3"

link_skill() { # dir
  mkdir -p "$1"
  local target="$1/herdr-delegate"
  if [ -L "$target" ] || [ ! -e "$target" ]; then
    ln -sfn "$here" "$target"; ok "linked $target"
  else
    warn "$target exists and is not a symlink; left it alone"
  fi
}
link_skill "$HOME/.claude/skills"
[ -d "$HOME/.codex" ] && link_skill "$HOME/.codex/skills"

chmod +x "$here/scripts/delegate" "$here/scripts/statusline-hook.sh"
if herdr plugin link "$here/plugin" >/dev/null 2>&1; then
  ok "linked Herdr plugin herdr-delegate.tree"
else
  warn "could not link the Herdr plugin; run: herdr plugin link $here/plugin"
fi

cat <<EOF

Remaining steps (manual, they touch your own config):
  1. Sidebar tree, colors, prefix+a panel, quota readout:
       paste $here/herdr/config-snippet.toml into ~/.config/herdr/config.toml
       then run: herdr server reload-config
  2. Usage-aware routing for Claude Code: in your statusline command, add
       echo "\$input" | ~/.claude/skills/herdr-delegate/scripts/statusline-hook.sh
     (Codex usage is read from ~/.codex/sessions automatically.)
  3. Optional, to delegate without being asked: add to ~/.claude/CLAUDE.md
     (and ~/.codex/AGENTS.md):
       Inside Herdr (HERDR_ENV=1), proactively use the herdr-delegate skill when a
       task has self-contained chunks; orchestrate and review yourself.
EOF
