#!/usr/bin/env bash
# Feed Claude Code's rate limits and context window to herdr-delegate's router.
#
# Claude Code pipes a JSON blob into your statusline command on every render.
# Pass that same blob to this script from your statusline, e.g.:
#
#   input=$(cat)
#   echo "$input" | ~/.claude/skills/herdr-delegate/scripts/statusline-hook.sh
#
# Best effort: never prints, never fails the statusline.
{
  d="${HERDR_DELEGATE_STATE:-$HOME/.cache/herdr-delegate}/usage"
  mkdir -p "$d"
  jq -c --arg pane "${HERDR_PANE_ID:-}" \
    '{at: (now|floor), pane: $pane, model: .model.id, rate_limits, context_window}' >"$d/.claude.$$" &&
    mv "$d/.claude.$$" "$d/claude.json"
  [ -n "${HERDR_PANE_ID:-}" ] && cp "$d/claude.json" "$d/ctx-${HERDR_PANE_ID//:/_}.json"
} >/dev/null 2>&1
exit 0
