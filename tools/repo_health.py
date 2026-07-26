#!/usr/bin/env python3
"""Structural health checks for this repo. Pure AST analysis - imports nothing from the game.

Catches the three failure modes that produced the duplication documented in AGENTS.md §10:

  1. SHADOWED   A .py file with the same name as a package. Python resolves the package
                first, so the module is unreachable. This is what made enemies.py,
                rendering/world.py and maps/editor.py look like working compat shims.
  2. UNREACHED  A module no entry point and no test can import. Dead weight that still
                shows up in greps and agent context.
  3. FORKED     The same substantial function defined in two different modules. This is
                how collision_projectiles.py and systems/collision/ drifted apart.

Runs with core deps only (stdlib) so CI stays green without pygame/torch/moderngl.

Usage:
    python tools/repo_health.py              # check against baseline, exit 1 on new violations
    python tools/repo_health.py --update     # rewrite baseline to current state
    python tools/repo_health.py --strict     # ignore baseline, fail on any violation
    python tools/repo_health.py --report     # human summary, always exit 0
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict, deque

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "repo_health_baseline.json")

# Directories never scanned.
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "build", "dist", ".pytest_cache"}

# Scripts that are legitimately roots of the import graph.
ENTRY_POINTS = ["game", "run_editor", "setup", "profile_game", "visualize"]

# Names that are meant to repeat - scene/system/screen interfaces, not forks.
INTERFACE_NAMES = {
    "main", "update", "render", "draw", "handle_input", "handle_event", "handle_events",
    "state_id", "reset", "close", "setup", "teardown", "run", "enter", "exit",
    "update_transition", "handle_input_transition", "on_enter", "on_exit",
}

# A duplicate only counts as a fork above this many lines. Short helpers repeat harmlessly.
FORK_MIN_LINES = 15


def discover(repo: str) -> dict[str, str]:
    """Map dotted module name -> file path. Packages win name collisions, as Python does."""
    mods: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            parts = os.path.relpath(full, repo)[:-3].split(os.sep)
            is_init = parts[-1] == "__init__"
            if is_init:
                parts = parts[:-1]
            name = ".".join(parts)
            if name in mods and not is_init:
                continue  # existing entry wins unless we are the package
            mods[name] = full
    return mods


def find_shadowed(repo: str) -> list[str]:
    """A foo.py sitting next to a foo/ package. The .py can never be imported."""
    out = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for d in dirnames:
            sibling = os.path.join(dirpath, d + ".py")
            if os.path.isfile(sibling) and os.path.isfile(os.path.join(dirpath, d, "__init__.py")):
                out.append(os.path.relpath(sibling, repo).replace(os.sep, "/"))
    return sorted(out)


def build_edges(mods: dict[str, str]) -> dict[str, set[str]]:
    """Import graph. Relative imports resolved against the containing package."""
    edges: dict[str, set[str]] = defaultdict(set)
    for name, path in mods.items():
        try:
            tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        if os.path.basename(path) == "__init__.py":
            pkg = name
        else:
            pkg = name.rsplit(".", 1)[0] if "." in name else ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    edges[name].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = pkg.split(".") if pkg else []
                    if node.level > 1:
                        base = base[: -(node.level - 1)]
                    target = ".".join([p for p in base if p] + ([node.module] if node.module else []))
                else:
                    target = node.module or ""
                edges[name].add(target)
                for alias in node.names:
                    edges[name].add(f"{target}.{alias.name}")
    return edges


def find_unreached(mods: dict[str, str], edges: dict[str, set[str]]) -> list[str]:
    """Modules no entry point and no test file can reach."""
    known = set(mods)

    def resolve(target: str) -> set[str]:
        hits = set()
        if target in known:
            hits.add(target)
        if "." in target and target.rsplit(".", 1)[0] in known:
            hits.add(target.rsplit(".", 1)[0])
        return hits

    roots = [e for e in ENTRY_POINTS if e in known]
    roots += [m for m in known if m.startswith("tests")]
    roots += [m for m in known if m.startswith("tools")]  # standalone tooling, not game code
    seen = set(roots)
    queue = deque(roots)
    while queue:
        for target in edges[queue.popleft()]:
            for hit in resolve(target):
                if hit not in seen:
                    seen.add(hit)
                    queue.append(hit)
    return sorted(known - seen)


def find_forks(mods: dict[str, str], repo: str) -> list[str]:
    """Substantial functions defined under the same name in two or more modules."""
    where: dict[str, list[str]] = defaultdict(list)
    for name, path in mods.items():
        try:
            tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
        if rel.startswith("tests/"):
            continue
        for node in tree.body:  # module-level only; methods legitimately repeat
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name in INTERFACE_NAMES or node.name.startswith("__"):
                continue
            end = max((getattr(n, "lineno", node.lineno) for n in ast.walk(node)), default=node.lineno)
            if end - node.lineno + 1 >= FORK_MIN_LINES:
                where[node.name].append(rel)
    return sorted(
        f"{fn} :: {', '.join(sorted(set(paths)))}"
        for fn, paths in where.items()
        if len(set(paths)) > 1
    )


def collect(repo: str) -> dict[str, list[str]]:
    mods = discover(repo)
    edges = build_edges(mods)
    return {
        "shadowed": find_shadowed(repo),
        "unreached": find_unreached(mods, edges),
        "forked": find_forks(mods, repo),
    }


HEADINGS = {
    "shadowed": "Shadowed modules (a .py next to a same-named package - unreachable)",
    "unreached": "Modules unreachable from any entry point or test",
    "forked": "Same function defined in multiple modules (possible fork)",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true", help="rewrite the baseline to current state")
    ap.add_argument("--strict", action="store_true", help="ignore baseline; fail on any violation")
    ap.add_argument("--report", action="store_true", help="print everything, always exit 0")
    args = ap.parse_args()

    current = collect(REPO)

    if args.update:
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=2, sort_keys=True)
            fh.write("\n")
        total = sum(len(v) for v in current.values())
        print(f"Baseline written: {BASELINE}")
        print(f"  {total} known violation(s) recorded. New ones will fail CI; these will not.")
        return 0

    if args.report:
        for key, heading in HEADINGS.items():
            print(f"\n{heading} - {len(current[key])}")
            for item in current[key]:
                print(f"  {item}")
        print()
        return 0

    baseline: dict[str, list[str]] = {k: [] for k in HEADINGS}
    if not args.strict:
        if os.path.exists(BASELINE):
            with open(BASELINE, encoding="utf-8") as fh:
                loaded = json.load(fh)
            baseline.update({k: loaded.get(k, []) for k in HEADINGS})
        else:
            print("No baseline found. Run: python tools/repo_health.py --update", file=sys.stderr)
            return 2

    new_violations = {k: sorted(set(current[k]) - set(baseline[k])) for k in HEADINGS}
    fixed = {k: sorted(set(baseline[k]) - set(current[k])) for k in HEADINGS}

    for key, items in fixed.items():
        for item in items:
            print(f"resolved  [{key}] {item}")
    if any(fixed.values()):
        print("\nSome baselined violations are gone. Run --update to lock in the progress.\n")

    failed = False
    for key, items in new_violations.items():
        if not items:
            continue
        failed = True
        print(f"\nNEW: {HEADINGS[key]}")
        for item in items:
            print(f"  {item}")

    if failed:
        print(
            "\nThese are new since the baseline. See AGENTS.md §10 - the fix is usually to\n"
            "delete the duplicate, not to add a compat shim. If a violation is intentional,\n"
            "run: python tools/repo_health.py --update\n"
        )
        return 1

    remaining = sum(len(v) for v in current.values())
    print(f"repo_health: OK - no new structural violations ({remaining} baselined remaining)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
