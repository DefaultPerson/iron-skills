#!/usr/bin/env python3
"""iron-skills plugin validator — structural + content invariants.

Single entry point, runnable locally (`python3 ci/validate.py`) and in CI.
Pure stdlib (no pyyaml) so it works without `pip install`. Exits non-zero on
any failure; prints one line per check.

Checks:
  1. Manifests parse; plugin name + version agree across plugin.json and
     marketplace.json (top name, plugins[0].name, plugins[0].version).
  2. skills/ and skills-codex/ hold the SAME set of skill names (parity), and
     install-codex.sh's SKILLS= list matches that set (the Codex install contract).
  3. Every skills|skills-codex/<n>/SKILL.md has frontmatter with a non-empty
     `name:` (== dir) and a `description:` of 1..1024 chars (Claude Code's cap).
  4. Every agents/*.md has frontmatter with `name:` (== filename) + description.
  5. Every commands/*.md has frontmatter with a non-empty `description:`.
  6. Cross-references resolve: agent-type refs `<x>:autoresearch-worker` use the
     current plugin name AND name a real agents/*.md; Workflow `scriptPath:`
     pointers resolve to a real file; no stale `ags:` / `/ags:` /
     `agent-goal-stack` / removed-`thermo` path refs.
  7. Syntax: every *.py compiles; every *.workflow.js parses (export-stripped,
     wrapped as the Workflow runtime wraps it); every *.sh passes `bash -n` —
     across functional dirs + repo root.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONAL_DIRS = ["skills", "skills-codex", "agents", "commands"]
DESC_CAP = 1024  # Claude Code rejects skill/agent descriptions longer than this at load.
# Skills that exist ONLY in the Claude tree (no Codex variant) — e.g. babysit
# needs the native /loop, which Codex lacks. Exempt from skills↔skills-codex parity.
CLAUDE_ONLY = {"babysit", "ship", "herdr"}

failures = []
checks = 0


def record(ok, name, detail=""):
    global checks
    checks += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def parse_frontmatter(text):
    """Minimal YAML-frontmatter key extractor (inline + block scalars)."""
    text = text.lstrip("﻿")  # tolerate a UTF-8 BOM
    if not text.startswith("---"):
        return None
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    block = lines[1:end]
    fm, i = {}, 0
    while i < len(block):
        line = block[i]
        m = re.match(r"^([A-Za-z0-9_-]+):(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key, inline = m.group(1), m.group(2).strip()
            vals = []
            if inline and inline not in (">", "|", "|-", ">-", "|+", ">+"):
                vals.append(inline)
            j = i + 1
            while j < len(block) and (block[j].startswith((" ", "\t")) or not block[j].strip()):
                if block[j].strip():
                    vals.append(block[j].strip())
                j += 1
            fm[key] = " ".join(vals).strip()
            i = j
        else:
            i += 1
    return fm


def collect(suffix):
    """Files with `suffix` across functional dirs + repo root (no __pycache__)."""
    out = set()
    for d in FUNCTIONAL_DIRS:
        out |= {p for p in (ROOT / d).rglob(f"*{suffix}") if "__pycache__" not in p.parts}
    out |= {p for p in ROOT.glob(f"*{suffix}")}
    return sorted(out)


def read(p):
    return p.read_text(errors="ignore")


def first_error(stderr):
    """The most useful line of a compiler/linter stderr (the error, not the version banner)."""
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    return next((ln for ln in lines if "Error" in ln), lines[0] if lines else "")


def rel(p):
    return p.relative_to(ROOT)


def section(title):
    print(f"\n== {title} ==")


def check_desc(fm, label):
    desc = (fm or {}).get("description", "")
    if not desc:
        record(False, label, "description MISSING")
    elif len(desc) > DESC_CAP:
        record(False, label, f"description {len(desc)} chars > {DESC_CAP} cap")
    return bool(desc) and len(desc) <= DESC_CAP


# ── 1. Manifests ──
section("manifests")
plugin = marketplace = plugin_name = None
try:
    plugin = json.loads(read(ROOT / ".claude-plugin" / "plugin.json"))
    record(True, "plugin.json parses")
except Exception as e:
    record(False, "plugin.json parses", str(e))
try:
    marketplace = json.loads(read(ROOT / ".claude-plugin" / "marketplace.json"))
    record(True, "marketplace.json parses")
except Exception as e:
    record(False, "marketplace.json parses", str(e))

if plugin and marketplace:
    mp0 = (marketplace.get("plugins") or [{}])[0]
    names = {plugin.get("name"), marketplace.get("name"), mp0.get("name")}
    record(len(names) == 1 and None not in names,
           "plugin name agrees (plugin==marketplace top==plugins[0])",
           str(sorted(map(str, names))))
    versions = {plugin.get("version"), mp0.get("version")}
    record(len(versions) == 1 and None not in versions,
           "version agrees (plugin.json==marketplace plugins[0])",
           str(sorted(map(str, versions))))
    plugin_name = plugin.get("name")

# Codex plugin manifest (skills-codex/.codex-plugin/plugin.json) + marketplace
# manifest (.agents/plugins/marketplace.json) must agree with the Claude side.
cx = cmkt = None
try:
    cx = json.loads(read(ROOT / "skills-codex" / ".codex-plugin" / "plugin.json"))
    record(True, ".codex-plugin/plugin.json parses")
except Exception as e:
    record(False, ".codex-plugin/plugin.json parses", str(e))
try:
    cmkt = json.loads(read(ROOT / ".agents" / "plugins" / "marketplace.json"))
    record(True, ".agents/plugins/marketplace.json parses")
except Exception as e:
    record(False, ".agents/plugins/marketplace.json parses", str(e))
if cx and plugin:
    record(cx.get("name") == plugin.get("name") and cx.get("version") == plugin.get("version"),
           "codex plugin.json name+version agree with .claude-plugin",
           f"codex={cx.get('name')}@{cx.get('version')} claude={plugin.get('name')}@{plugin.get('version')}")
    record(cx.get("skills") == "./", 'codex plugin.json skills == "./"', str(cx.get("skills")))
if cmkt and plugin_name:
    cp0 = (cmkt.get("plugins") or [{}])[0]
    src = (cp0.get("source") or {}).get("path")
    record(cp0.get("name") == plugin_name and src == "./skills-codex",
           'codex marketplace plugins[0] name + source.path == "./skills-codex"',
           f"name={cp0.get('name')} path={src}")

# ── 2. parity (skills ↔ skills-codex ↔ install-codex.sh) ──
section("skills ↔ skills-codex ↔ install-codex.sh parity")
sk = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir() and not p.name.startswith(".")}
ck = {p.name for p in (ROOT / "skills-codex").iterdir() if p.is_dir() and not p.name.startswith(".")}
record((sk - CLAUDE_ONLY) == ck, "skills-codex/ mirrors skills/ (Claude-only exempt)",
       (f"claude-only-extra: {sorted((sk - CLAUDE_ONLY) - ck)} | codex-only: {sorted(ck - (sk - CLAUDE_ONLY))}") if (sk - CLAUDE_ONLY) != ck else f"{len(ck)} shared skills")
record(CLAUDE_ONLY <= sk and not (CLAUDE_ONLY & ck), "Claude-only skills present in skills/, absent from skills-codex/",
       f"{sorted(CLAUDE_ONLY)} | missing-from-skills: {sorted(CLAUDE_ONLY - sk)} | leaked-into-codex: {sorted(CLAUDE_ONLY & ck)}")

sh_path = ROOT / "install-codex.sh"
sh_text = read(sh_path) if sh_path.exists() else ""
m = re.search(r'^SKILLS="([^"]*)"', sh_text, re.M)
if m:
    skills_list = set(m.group(1).split())
    record(skills_list == ck, "install-codex.sh SKILLS == skills-codex/ dirs",
           (f"only-in-SKILLS: {sorted(skills_list - ck)} | missing-from-SKILLS: {sorted(ck - skills_list)}") if skills_list != ck else f"{len(skills_list)} skills")
else:
    record(False, "install-codex.sh SKILLS= line found")

# ── 3. SKILL.md frontmatter ──
section("SKILL.md frontmatter (name==dir, description 1..%d chars)" % DESC_CAP)
for tree in ("skills", "skills-codex"):
    for d in sorted(p for p in (ROOT / tree).iterdir() if p.is_dir() and not p.name.startswith(".")):
        f = d / "SKILL.md"
        label = f"{tree}/{d.name}/SKILL.md"
        if not f.exists():
            record(False, label, "missing")
            continue
        fm = parse_frontmatter(read(f))
        if fm is None:
            record(False, label, "no --- frontmatter block")
            continue
        if fm.get("name") != d.name:
            record(False, label, f"name={fm.get('name')!r} != dir {d.name!r}")
            continue
        if check_desc(fm, label):
            record(True, label)

# ── 4. agents ──
section("agents/*.md frontmatter")
for f in sorted((ROOT / "agents").glob("*.md")):
    label = f"agents/{f.name}"
    fm = parse_frontmatter(read(f))
    if fm is None:
        record(False, label, "no --- frontmatter block")
        continue
    if fm.get("name") != f.stem:
        record(False, label, f"name={fm.get('name')!r} != file {f.stem!r}")
        continue
    if check_desc(fm, label):
        record(True, label)

# ── 5. commands ──
section("commands/*.md frontmatter (description present)")
for f in sorted((ROOT / "commands").glob("*.md")):
    label = f"commands/{f.name}"
    fm = parse_frontmatter(read(f))
    if check_desc(fm, label):
        record(True, label)

# ── 6. cross-references + namespace hygiene ──
section("cross-references + namespace hygiene")
text_files = [p for d in FUNCTIONAL_DIRS for p in (ROOT / d).rglob("*")
              if p.is_file() and p.suffix in (".md", ".js", ".py", ".sh", ".json")]

stale_patterns = {
    "stale `ags:` agent ref": re.compile(r"(?<![\w/])ags:"),
    "stale `/ags:` command ref": re.compile(r"/ags:"),
    "stale `agent-goal-stack`": re.compile(r"\bagent-goal-stack\b"),
    # the LOCAL thermo skill was removed in v5; guard its path/command forms,
    # not prose attribution to the upstream Cursor skill it was sourced from.
    "removed `thermo` skill path/command": re.compile(r"/thermo|skills(-codex)?/thermo"),
}
for label, pat in stale_patterns.items():
    hits = [f"{rel(p)}:{n}" for p in text_files
            for n, line in enumerate(read(p).splitlines(), 1) if pat.search(line)]
    record(not hits, f"no {label}", " ".join(hits[:5]))

agent_stems = {f.stem for f in (ROOT / "agents").glob("*.md")}
if plugin_name:
    # any `<x>:autoresearch-worker` must use the current plugin name as prefix
    aw = re.compile(r"([A-Za-z0-9_-]+):autoresearch-worker")
    bad_prefix = [f"{rel(p)}:{n} ({mm.group(1)})" for p in text_files
                  for n, line in enumerate(read(p).splitlines(), 1)
                  for mm in aw.finditer(line) if mm.group(1) != plugin_name]
    record(not bad_prefix, f"autoresearch-worker agent-type prefix == '{plugin_name}'", " ".join(bad_prefix[:5]))

    # any `<plugin>:<stem>` agent-type ref must resolve to a real agents/*.md
    own = re.compile(rf"\b{re.escape(plugin_name)}:([A-Za-z0-9_-]+)")
    dangling = [f"{rel(p)}:{n} ({mm.group(1)})" for p in text_files
                for n, line in enumerate(read(p).splitlines(), 1)
                for mm in own.finditer(line) if mm.group(1) not in agent_stems]
    record(not dangling, f"'{plugin_name}:<agent>' refs resolve to agents/ ({sorted(agent_stems)})", " ".join(dangling[:5]))

# Workflow scriptPath: pointers resolve relative to the referencing SKILL.md
sp = re.compile(r'scriptPath:\s*["\']([^"\']+)["\']')
bad_paths = []
for tree in ("skills", "skills-codex"):
    for f in (ROOT / tree).rglob("SKILL.md"):
        for n, line in enumerate(read(f).splitlines(), 1):
            for mm in sp.finditer(line):
                if not (f.parent / mm.group(1)).exists():
                    bad_paths.append(f"{rel(f)}:{n} -> {mm.group(1)}")
record(not bad_paths, "Workflow scriptPath: pointers resolve", " ".join(bad_paths[:5]))

# ── 6b. Codex packaging: skills-codex assets are self-contained + in sync ──
# `codex plugin add` copies the plugin and strips symlinks, so each Codex skill
# carries real copies of its references/scripts/templates/roles (built by
# ci/build-codex.sh from skills/). Assert no drift, and that workflows/ (no
# Workflow tool on Codex) never leaks into the Codex tree.
section("codex packaging (skills-codex assets in sync with skills/)")
CODEX_ASSETS = ("references", "scripts", "templates", "roles")
drift = []
for name in sorted(ck):
    for sub in CODEX_ASSETS:
        cdir = ROOT / "skills-codex" / name / sub
        if not cdir.is_dir():
            continue
        for cf in cdir.rglob("*"):
            if cf.is_file() and "__pycache__" not in cf.parts:
                srcf = ROOT / "skills" / name / cf.relative_to(ROOT / "skills-codex" / name)
                if not srcf.is_file() or srcf.read_bytes() != cf.read_bytes():
                    drift.append(str(cf.relative_to(ROOT)))
record(not drift, "skills-codex assets byte-identical to skills/ (run ci/build-codex.sh)", " ".join(drift[:5]))
wf_leak = [str(p.relative_to(ROOT)) for p in (ROOT / "skills-codex").rglob("workflows") if p.is_dir()]
record(not wf_leak, "no workflows/ under skills-codex (Codex has no Workflow tool)", " ".join(wf_leak[:5]))

# ── 7. syntax (py / workflow js / bash) across functional dirs + root ──
section("syntax (py / workflow js / bash)")
for py in collect(".py"):
    r = subprocess.run([sys.executable, "-m", "py_compile", str(py)], capture_output=True, text=True)
    record(r.returncode == 0, f"py_compile {rel(py)}", first_error(r.stderr) if r.returncode else "")

WF_WRAP_HEAD = "async function __wf(args, parallel, agent, phase, log, budget, pipeline, workflow){\n"
for js in [p for p in collect(".js") if p.name.endswith(".workflow.js")]:
    # The runtime wraps the body in an async fn; strip `export` (illegal inside a
    # function body, and — critically — its presence makes `node --check` a no-op
    # that swallows downstream syntax errors) so the parse actually validates.
    body = re.sub(r"^export\s+", "", read(js), flags=re.M)
    wrapped = WF_WRAP_HEAD + body + "\n}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=True) as tmp:
        tmp.write(wrapped)
        tmp.flush()
        r = subprocess.run(["node", "--check", tmp.name], capture_output=True, text=True)
    record(r.returncode == 0, f"node --check {rel(js)} (wrapped)",
           first_error(r.stderr) if r.returncode else "")

for sh in collect(".sh"):
    r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
    record(r.returncode == 0, f"bash -n {rel(sh)}", r.stderr.strip() if r.returncode else "")

# ── summary ──
print("\n" + "=" * 48)
if failures:
    print(f"FAILED — {len(failures)}/{checks} checks failed:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"OK — all {checks} checks passed.")
