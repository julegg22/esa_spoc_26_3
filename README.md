# esa_spoc_26 — SpOC4 campaign

Personal campaign for ESA's [Space Optimisation Competition 4 (SpOC4)](https://www.esa.int/gsp/ACT/news/spoc-2026/). Submissions open 2026-04-01; deadline **2026-06-30 AoE**.

## Orientation

- **Process rules.** [`CLAUDE.md`](CLAUDE.md) (coding discipline) + [`META.md`](META.md) (research discipline — scientific method as tree search over hypothesis space).
- **Current state.** Start at [`vault/index.md`](vault/index.md); the live frontier is [`vault/open-paths.md`](vault/open-paths.md). The most recent "Dated changes" entry there names the active hypothesis.
- **Grounding.** Observations in `vault/observations/`, engineering lessons in `vault/lessons/`, prior-knowledge concepts in `vault/concepts/`, methodology insights in `vault/methodology/`, package docs in `vault/package/`.

## Setup on a new machine

```bash
git clone https://github.com/julegg22/esa_spoc_26.git
cd esa_spoc_26

# 1. Upstream starter kit (gitignored — must be re-cloned locally)
git clone --depth 1 https://github.com/esa/SpOC4.git reference/SpOC4

# 2. Pre-commit hooks
pip install pre-commit
pre-commit install
```

**Python env.** Per [`vault/lessons/L-001-windows-requires-miniforge.md`](vault/lessons/L-001-windows-requires-miniforge.md): miniforge + Python 3.13 + conda-forge science stack. The concrete `environment.yml` lands with **H-001** — see [`vault/hypotheses/H-001-windows-miniforge-env-works.md`](vault/hypotheses/H-001-windows-miniforge-env-works.md). On Linux this decision may be revisited; update or supersede L-001 as needed.

**Claude Code skills.** The repo ships project-local skills under [`.claude/skills/`](.claude/skills/). Claude Code auto-discovers them in this directory; no separate install step. Restart the Claude Code session after fresh clone so the skills appear in the available-skills list. Current set:

| skill                  | purpose                                                                                  |
| ---------------------- | ---------------------------------------------------------------------------------------- |
| `excalidraw-diagram`   | Draw architecture / process / experiment diagrams as `.excalidraw.md` (+ PNG export).    |
| `obsidian-markdown`    | Edit Obsidian-flavored markdown — wikilinks, embeds, callouts, properties.               |
| `obsidian-bases`       | Author / tweak `frontier.base` and other Obsidian Bases (`.base`) views.                 |
| `json-canvas`          | Edit Obsidian JSON canvas (`.canvas`) files — graph-style visual maps.                   |
| `obsidian-cli`         | Interact with Obsidian vaults via the Obsidian CLI; plugin / theme dev.                  |
| `defuddle`             | Extract clean Markdown from web pages (token-efficient ingestion of external articles).  |

To add a new skill: drop `<skill-name>/SKILL.md` into `.claude/skills/`, restart Claude Code, commit. (Avoid embedding upstream `.git/` directories — track skill files as plain files.)

## Repo layout

```
CLAUDE.md              coding discipline
META.md                research discipline
pyproject.toml         ruff config + project metadata
.pre-commit-config.yaml  ruff + hygiene hooks
.claude/
└── skills/            project-local Claude Code skills (excalidraw, obsidian-*, etc.)
src/                   code (starts minimal; grows per hypothesis)
solutions/             submission JSON files (committed before any POST to Optimise)
vault/                 Obsidian-compatible research log
├── index.md           campaign root
├── open-paths.md      live frontier (embeds frontier.base)
├── frontier.base      Obsidian Bases view over hypotheses
├── user.md            user profile + soft preferences (portable cross-machine)
├── observations/      O-NNN — grounding facts (append-only)
├── questions/         Q-NNN — precise ambiguities
├── hypotheses/        H-NNN — falsifiable claims
├── experiments/       E-NNN — runs, metrics, plots
├── takeaways/         T-NNN — distilled problem-side learnings (≥ 1 per closed H)
├── lessons/           L-NNN — engineering lessons (gotchas, ADRs)
├── concepts/          C-NNN — prior-knowledge primers (domain + tool)
├── methodology/       M-NNN — methodology insights (publication-bound)
├── sessions/          S-YYYY-MM-DD — episodic session narratives (tier-2 memory)
├── package/           living software docs
├── reviews/           weekly + milestone retrospectives
└── _templates/        copy-and-fill templates (one per node type)
reference/             (gitignored) upstream starter kits — re-clone
```
