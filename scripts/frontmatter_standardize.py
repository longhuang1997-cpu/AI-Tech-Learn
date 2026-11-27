"""
AI Tech Learn - Frontmatter Standardizer
Normalizes Obsidian frontmatter fields across your vault.

Usage:
    python frontmatter_standardize.py <vault_path> [--apply]

    --apply   Actually write changes (default is dry-run, only prints what would change)

Examples:
    python frontmatter_standardize.py "/home/user/Obsidian Vault"
    python frontmatter_standardize.py "/home/user/Obsidian Vault" --apply
"""

import os
import re
import sys
import shutil
from pathlib import Path
from datetime import datetime

DRY_RUN       = True   # overridden by --apply flag
CREATE_BACKUP = True

# type field normalization — extend or override for your vault's conventions
TYPE_MAPPING = {
    "weekly-review":  "weekly",
    "ai-method":      "paradigm",
    "ai-tech-dialogue": "dialogue",
    "partner-档案":   "person",
    "book-note":      "book",
    "product-snapshot": "project",
    "prd":            "project",
    "roadmap":        "project",
    "metrics":        "project",
    "backlog":        "project",
    "architecture":   "project",
    "risks":          "project",
    "stakeholders":   "project",
    "agent-prompt":   "project",
    "wiki-page":      "wiki",
    "memory-bridge":  "reference",
    "health-check-report": "health-report",
}

# date field rename: updated → last-updated
DATE_FIELD_MAPPING = {"updated": "last-updated"}


def extract_frontmatter(content):
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return None, content
    return match.group(1), content[match.end():]


def update_frontmatter(fm_text):
    changes = []
    new_lines = []

    for line in fm_text.split("\n"):
        line = line.strip()
        if not line:
            new_lines.append(line)
            continue

        m = re.match(r"^type:\s*(.+)$", line, re.IGNORECASE)
        if m:
            raw   = m.group(1).strip().strip("\"'")
            if raw in TYPE_MAPPING:
                new_lines.append(f"type: {TYPE_MAPPING[raw]}")
                changes.append(f"type: {raw} → {TYPE_MAPPING[raw]}")
            else:
                new_lines.append(line)
            continue

        m = re.match(r"^updated:\s*(.+)$", line, re.IGNORECASE)
        if m:
            new_lines.append(f"last-updated: {m.group(1)}")
            changes.append(f"updated → last-updated: {m.group(1)}")
            continue

        new_lines.append(line)

    return "\n".join(new_lines), changes


def add_frontmatter_to_daily(content, file_path):
    filename   = Path(file_path).stem
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    date       = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")
    header     = f"---\ntype: daily\nstatus: reference\ncreated: {date}\nlast-updated: {date}\ntags: [daily]\n---\n\n"
    return header + content, ["added frontmatter (daily note)"]


def process_file(file_path, vault_dir):
    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except Exception as e:
        return None, [f"read error: {e}"]

    is_daily = "40_Daily" in str(file_path)
    fm_text, body = extract_frontmatter(content)

    if fm_text is None:
        if is_daily:
            return add_frontmatter_to_daily(content, file_path)
        return None, []

    new_fm, changes = update_frontmatter(fm_text)
    if not changes:
        return None, []

    return f"---\n{new_fm}\n---\n{body}", changes


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    vault_dir = Path(sys.argv[1])
    global DRY_RUN
    DRY_RUN = "--apply" not in sys.argv

    if not vault_dir.is_dir():
        print(f"Error: '{vault_dir}' is not a directory.")
        sys.exit(1)

    backup_dir = None
    if CREATE_BACKUP and not DRY_RUN:
        backup_dir = vault_dir / "05_Improved" / f"_backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"Backup directory: {backup_dir.relative_to(vault_dir)}")

    total = changed = 0
    all_changes = []

    for md_file in vault_dir.rglob("*.md"):
        if ".git" in str(md_file):
            continue
        if backup_dir and str(md_file).startswith(str(backup_dir)):
            continue

        total += 1
        new_content, file_changes = process_file(md_file, vault_dir)
        if not file_changes:
            continue

        changed += 1
        all_changes.append(f"\n📄 {md_file.relative_to(vault_dir)}")
        all_changes.extend(f"   {c}" for c in file_changes)

        if not DRY_RUN and new_content:
            if CREATE_BACKUP and backup_dir:
                dest = backup_dir / md_file.relative_to(vault_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(md_file, dest)
            md_file.write_text(new_content, encoding="utf-8")

    print(f"\n=== Done ===")
    print(f"Files scanned:  {total}")
    print(f"Files to change:{changed}")
    print(f"Mode: {'DRY RUN (no files changed)' if DRY_RUN else 'APPLIED'}")

    if all_changes:
        print("\n=== Changes ===")
        print("\n".join(all_changes[:100]))
        if len(all_changes) > 100:
            print(f"... and {len(all_changes)-100} more")

    if DRY_RUN:
        print("\nRe-run with --apply to write changes.")


if __name__ == "__main__":
    main()
