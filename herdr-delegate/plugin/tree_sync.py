#!/usr/bin/env python3
"""Project delegate subagents into Herdr's Agents panel as a tree.

Herdr has no parent/child relation between agents, so this fakes one with
display-only pane metadata plus an agent view sort:

  * every top-level agent gets $space/$tabl tokens (its header row) and a
    $tree sort key like "0001";
  * every child spawned by `delegate` gets $tree = "<parent key>/00", a
    $branch glyph and $model, and no $space/$tabl, so its header row
    disappears and it renders as one indented line under its parent;
  * agent.view.set sorts by workspace_order, then $tree.

Idempotent; run it after any change (the plugin's event hooks and the
delegate script both do).
"""
import fcntl
import glob
import json
import os
import socket
import subprocess
import sys

SOURCE = "herdr-tree"
STATE_DIR = os.environ.get("HERDR_DELEGATE_STATE", os.path.expanduser("~/.cache/herdr-delegate"))
HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")
SOCK = os.environ.get("HERDR_SOCKET_PATH") or os.path.expanduser("~/.config/herdr/herdr.sock")


def cli(*args):
    out = subprocess.run([HERDR, *args], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {}


def rpc(method, params):
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(SOCK)
        s.sendall((json.dumps({"id": SOURCE, "method": method, "params": params}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf or b"{}")


def pane_num(pane_id):
    # Pane suffixes run 1-9 then A-Z..., i.e. base 36.
    return int(pane_id.rsplit(":p", 1)[-1], 36)


def load_registry(live_panes):
    reg = {}
    for path in glob.glob(os.path.join(STATE_DIR, "*.json")):
        try:
            entry = json.load(open(path))
        except (OSError, ValueError):
            continue
        name = os.path.basename(path)[:-5]
        if entry.get("pane") not in live_panes:
            os.remove(path)  # child exited or pane closed
            continue
        reg[entry["pane"]] = dict(entry, name=name)
    return reg


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    lock = open(os.path.join(STATE_DIR, ".tree.lock"), "w")
    fcntl.flock(lock, fcntl.LOCK_EX)

    agents = cli("agent", "list").get("result", {}).get("agents", [])
    live = {a["pane_id"]: a for a in agents}
    reg = load_registry(live)

    workspaces = {w["workspace_id"]: w for w in cli("workspace", "list").get("result", {}).get("workspaces", [])}
    tabs = {}
    for ws in workspaces:
        for t in cli("tab", "list", "--workspace", ws).get("result", {}).get("tabs", []):
            tabs[t["tab_id"]] = t
    # Show the tab label only where it disambiguates (more than one real tab).
    real_tabs = {}
    for t in tabs.values():
        if t["label"] != "subagents":
            real_tabs[t["workspace_id"]] = real_tabs.get(t["workspace_id"], 0) + 1

    children = {}
    for pane, entry in reg.items():
        parent = entry.get("parent")
        if parent in live:
            children.setdefault(parent, []).append(pane)
    for kids in children.values():
        kids.sort(key=pane_num)

    reports = {}

    def walk(pane, key, depth, last):
        entry = reg.get(pane)
        if entry and depth > 0:
            model = entry.get("model") or entry.get("kind")
            # The model sits on its own row under the name. Bake the tree stem
            # and indent into the value: separate tokens would get a " · "
            # separator between them. Herdr trims Unicode whitespace (NBSP too), so
            # pad with U+2800 BRAILLE BLANK, which renders empty but is not whitespace.
            pad = "\u2800" * 3 * (depth - 1)
            stem = pad + ("\u2800" if last else "│") + "\u2800" * 6
            reports[pane] = {
                "display_agent": entry["name"],
                "tokens": {
                    "tree": key,
                    "branch": pad + ("└─" if last else "├─"),
                    "model": stem + model + (f"/{entry['effort']}" if entry.get("effort") else ""),
                    "prov": entry.get("kind"),
                    "space": None, "tabl": None,
                },
            }
        else:
            a = live[pane]
            ws = workspaces.get(a["workspace_id"], {})
            tab = tabs.get(a["tab_id"], {})
            reports[pane] = {
                "tokens": {
                    "tree": key,
                    "space": ws.get("label") or a["workspace_id"],
                    "tabl": tab.get("label") if real_tabs.get(a["workspace_id"], 0) > 1 else None,
                    "branch": None, "model": None, "prov": None,
                },
            }
        kids = children.get(pane, [])
        for i, kid in enumerate(kids):
            walk(kid, f"{key}/{i:02d}", depth + 1, i == len(kids) - 1)

    roots = [p for p in live if not (p in reg and reg[p].get("parent") in live)]
    for pane in sorted(roots, key=pane_num):
        walk(pane, f"{pane_num(pane):04d}", 0, True)

    for pane, rep in reports.items():
        params = {"pane_id": pane, "source": SOURCE, "tokens": rep["tokens"]}
        if "display_agent" in rep:
            params["display_agent"] = rep["display_agent"]
        rpc("pane.report_metadata", params)

    rpc("agent.view.set", {
        "source": SOURCE,
        "label": "tree",
        "sort": [
            {"field": "workspace_order", "order": "asc"},
            {"field": {"token": "tree"}, "order": "asc"},
        ],
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the caller (event hook or delegate)
        print(f"tree_sync: {e}", file=sys.stderr)
        sys.exit(0)
