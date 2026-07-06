# iron-skills

Battle-tested skills for AI coding agents — Claude Code and Codex CLI. Only the ones I actually use, kept lean.

> Formerly `agent-skills` (renamed to dodge the reserved install name). Repo, plugin, and marketplace are all `iron-skills`.

## Flow

Full — messy input to shipped + verified:

```
cleanup → extract-links → blueprint → goal-prep → /goal → verify-done
```

Small task — skip the heavy prep:

```
native plan mode → implement → verify-done
```

The steps chain, but each works on its own — run one or the whole line. `verify-done` takes a `/blueprint` plan, a `goal.md`, or just a plan-mode/inline plan.

Or hand the whole thing off:

```
/ship «your task»  →  it picks the chain and runs to a verified finish
```

`/ship` asks once how autonomous to be (guided / autopilot / checkpoint), then routes and runs end-to-end. Claude Code only. ⚠️ **Experimental** — newest skill, not yet battle-tested; prefer `guided`/`checkpoint` and review what it does.

## Skills

- **`/ship`** *(the autopilot — ⚠️ experimental, not yet battle-tested)* — hand it a whole task and it picks which of the skills below to run, chains them, and drives to a verified finish; asks once how hands-off to be. Claude Code only. *e.g. `/ship «add dark mode and make sure it works»` → it plans, builds, and verifies, mostly unattended.*
- **`/cleanup`** — tidy a messy notes or chat dump into a clean, well-structured doc, without dropping anything. *e.g. a long brain-dump → an organized file with clear headings, every link and detail kept.*
- **`/extract-links`** — bring what's behind the links in a note into the note itself, so you don't open each one. Adds a one-line summary next to every link by default; `--full` saves the full text (YouTube transcripts, Telegram posts, articles) locally. *e.g. `/extract-links notes.md` → each URL gets a "what this is" note inline.*
- **`/blueprint`** — turn a rough spec into a clear step-by-step plan: small tasks, each with a one-line "done when this command passes" check. *e.g. `/blueprint feature.md` → a task list you or an agent can build and verify.*
- **`/goal-prep`** — write the brief for Claude Code's built-in `/goal` so an autonomous run knows exactly when it's finished. It only prepares the brief — it doesn't run anything. *e.g. hand it a plan → get a ready-to-paste `/goal` command with clear "done" criteria.*
- **`/autoresearch`** — improve a number on its own: try one change at a time, keep it if the metric got better, revert if not — looping until it stops improving. *e.g. "make this benchmark faster" → it experiments commit by commit, unattended.*
- **`/verify-done`** — check whether work is *actually* finished, not just "looks done": re-runs the plan's checks, tries cases the plan may have missed, and flags quality issues. Read-only — answers DONE / NOT-DONE with a list of gaps. *e.g. after building a feature → it tells you what still doesn't work.*
- **`/svgl`** — grab brand/tech logos as SVGs straight into your project. *e.g. `/svgl github stripe` → the logos saved as `.svg` files.*

Plus **`/babysit`** (Claude Code only) — watch a running service and keep it alive unattended: every few minutes it checks logs and health, and on trouble it fixes, deploys, and re-checks — beeping for you only when it's truly stuck. *e.g. point it at your prod app → it self-heals and pings you only on a real fire.*

And **`/herdr`** *(Claude Code · needs the [herdr](https://herdr.dev) multiplexer, runs only inside a herdr pane)* — drive the whole terminal from the CLI: split panes, spawn sibling agents (more Claude Code sessions, servers, tests), read another pane's output, and block until a command is ready or another agent is done. Adapted from herdr's upstream skill. *e.g. start a dev server in a sibling pane, wait for "ready", then hand a second agent a task.*

## Install

Native plugin install — paste the line for your runtime, then restart the session:

```bash
# Claude Code
claude plugin marketplace add DefaultPerson/iron-skills && claude plugin install iron-skills@iron-skills

# Codex CLI
codex plugin marketplace add https://github.com/DefaultPerson/iron-skills && codex plugin add iron-skills@iron-skills
```

No-marketplace fallback: `git clone` the repo, then symlink `skills/*` into `~/.claude/skills/` (Claude Code) or run `bash install-codex.sh` (Codex).

## Prerequisites

`git`, `bash`, `jq`, `python3`. `/extract-links` probes for `yt-dlp` (YouTube) and `pandoc` (HTML, optional) at runtime. `/blueprint`'s cross-model review is optional — it calls the *other* CLI (Codex when running in Claude Code, Claude when running in Codex) plus an optional `OPENROUTER_API_KEY` third reviewer; without them it falls back to single-model validation. `/herdr` needs the [`herdr`](https://herdr.dev) binary and only activates inside a herdr pane (`HERDR_ENV=1`).

Release history: see [CHANGELOG.md](CHANGELOG.md).
