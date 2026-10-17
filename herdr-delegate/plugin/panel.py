#!/usr/bin/env python3
"""Subagents panel: a live, colored tree of orchestrators and their delegate
children. Opens as a Herdr plugin popup. Keys: 1-9 focus that child, q/esc close."""
import glob
import json
import os
import select
import subprocess
import sys
import termios
import time
import tty

HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")
STATE_DIR = os.environ.get("HERDR_DELEGATE_STATE", os.path.expanduser("~/.cache/herdr-delegate"))

RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"


def rgb(h):
    h = h.lstrip("#")
    return "\033[38;2;{};{};{}m".format(*(int(h[i:i + 2], 16) for i in (0, 2, 4)))


# Keep in sync with the [ui.sidebar.agents] rules in ~/.config/herdr/config.toml.
MODEL_COLORS = [
    ("opus", "#f38ba8"), ("sonnet", "#fab387"), ("haiku", "#a6e3a1"),
    ("gpt-6-astra", "#cba6f7"), ("gpt-6.1-sol", "#89b4fa"), ("gpt-6-sol", "#89b4fa"),
    ("gpt-6-luna", "#94e2d5"), ("gemini", "#f9e2af"),
]
STATUS = {
    "working": ("◐", "#f9e2af"), "blocked": ("■", "#f38ba8"), "done": ("●", "#a6e3a1"),
    "idle": ("○", "#7f849c"), "unknown": ("?", "#7f849c"),
}


def model_color(model):
    for prefix, color in MODEL_COLORS:
        if (model or "").startswith(prefix):
            return rgb(color)
    return ""


def cli(*args):
    out = subprocess.run([HERDR, *args], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {}


def elapsed(start):
    s = int(time.time() - start) if start else 0
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


def render(width):
    agents = {a["pane_id"]: a for a in cli("agent", "list").get("result", {}).get("agents", [])}
    spaces = {w["workspace_id"]: w["label"] for w in cli("workspace", "list").get("result", {}).get("workspaces", [])}
    reg = []
    for path in glob.glob(os.path.join(STATE_DIR, "*.json")):
        try:
            e = json.load(open(path))
        except (OSError, ValueError):
            continue
        if e.get("pane") in agents:
            reg.append(dict(e, name=os.path.basename(path)[:-5]))
    by_parent = {}
    for e in reg:
        by_parent.setdefault(e.get("parent"), []).append(e)

    lines = [f"{BOLD}subagents{RESET}  {DIM}1-9 focus · q close{RESET}", ""]
    targets = []
    if not reg:
        lines.append(f"{DIM}no delegate children running{RESET}")
    for parent, kids in sorted(by_parent.items(), key=lambda kv: kv[0] or ""):
        p = agents.get(parent, {})
        icon, color = STATUS.get(p.get("agent_status"), STATUS["unknown"])
        space = spaces.get(p.get("workspace_id"), p.get("workspace_id", "?"))
        lines.append(f"{rgb(color)}{icon}{RESET} {BOLD}{space}{RESET} {DIM}{p.get('agent', 'orphaned')}{RESET}")
        for i, e in enumerate(sorted(kids, key=lambda e: e.get("started", 0))):
            a = agents[e["pane"]]
            icon, color = STATUS.get(a.get("agent_status"), STATUS["unknown"])
            targets.append(e["name"])
            branch = "└─" if i == len(kids) - 1 else "├─"
            model = e.get("model") or e.get("kind")
            head = (f"{DIM}{branch}{RESET} {DIM}{len(targets)}{RESET} {rgb(color)}{icon}{RESET} "
                    f"{BOLD}{e['name']}{RESET} {model_color(model)}{model}/{e.get('effort', '')}{RESET} "
                    f"{DIM}{elapsed(e.get('started'))}{RESET}")
            lines.append(head)
            task = (e.get("task") or "")[: max(10, width - 8)]
            lines.append(f"{DIM}{'   ' if i == len(kids) - 1 else '│  '}  {task}{RESET}")
        lines.append("")
    return lines, targets


def main():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    sys.stdout.write("\033[?25l")
    try:
        while True:
            cols = os.get_terminal_size().columns
            lines, targets = render(cols)
            sys.stdout.write("\033[H\033[2J" + "\n".join(lines))
            sys.stdout.flush()
            r, _, _ = select.select([sys.stdin], [], [], 1.0)
            if not r:
                continue
            key = os.read(fd, 8).decode(errors="ignore")
            if key in ("q", "\x1b"):
                return
            if key.isdigit() and 0 < int(key) <= len(targets):
                cli("agent", "focus", targets[int(key) - 1])
                return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\033[?25h" + RESET)


if __name__ == "__main__":
    main()
