# my-skills

Agent skills I've built for Claude Code and Codex. Each folder is self-contained: a `SKILL.md` for the agent, plus whatever scripts it needs, and a README for humans.

| Skill | What it does |
|---|---|
| [herdr-delegate](herdr-delegate/) | An expensive model orchestrates while cheaper Claude/GPT/Gemini helpers do the routine work, each visible as a Herdr pane nested under its orchestrator. Usage-aware routing keeps GPT working alongside Claude. |

## Installing a skill

Each skill has its own install steps in its README. In general, a skill is a folder linked into your agent's skills directory:

```bash
git clone https://github.com/Arluigi/my-skills ~/code/my-skills
ln -s ~/code/my-skills/<skill> ~/.claude/skills/<skill>   # Claude Code
ln -s ~/code/my-skills/<skill> ~/.codex/skills/<skill>    # Codex
```

Use symlinks so a `git pull` updates the skill in place.

## License

MIT
