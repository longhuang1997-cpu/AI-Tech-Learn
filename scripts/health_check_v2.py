"""
AI Tech Learn - Knowledge Health Check Tool v2.0
Scans methodology library and MOC, generates health report.

Usage:
    python health_check_v2.py <vault_path>
    python health_check_v2.py "/path/to/your/Obsidian Vault"
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

# Folder name defaults — override via env vars if your vault uses different names
METHODOLOGY_FOLDER = os.environ.get("AI_TECH_METHODOLOGY_FOLDER", "04_AI_Capability_Library/Methodology")
MOC_FOLDER         = os.environ.get("AI_TECH_MOC_FOLDER",          "60_MOC")
REPORT_FOLDER      = os.environ.get("AI_TECH_REPORT_FOLDER",       METHODOLOGY_FOLDER)


class KnowledgeHealthCheckerV2:
    def __init__(self, vault_dir: str):
        self.vault_dir       = Path(vault_dir)
        self.methodology_dir = self.vault_dir / Path(METHODOLOGY_FOLDER)
        self.moc_dir         = self.vault_dir / Path(MOC_FOLDER)
        self.report_date     = datetime.now().strftime("%Y-%m-%d")

    # ── Methodology scan ─────────────────────────────────────────────────────

    def scan_methodologies(self) -> List[Dict]:
        methodologies = []
        if not self.methodology_dir.exists():
            return methodologies

        for md_file in self.methodology_dir.rglob("*.md"):
            if md_file.name in ["README.md"] or "Template" in md_file.name \
                    or md_file.name.startswith("_health-report"):
                continue
            try:
                content     = md_file.read_text(encoding="utf-8")
                frontmatter = self._extract_frontmatter(content)
                stat        = md_file.stat()
                methodologies.append({
                    "path":          md_file,
                    "name":          md_file.stem,
                    "domain":        self._extract_domain(md_file, self.methodology_dir),
                    "type":          frontmatter.get("type", "methodology"),
                    "created":       frontmatter.get("created", "unknown"),
                    "last_modified": datetime.fromtimestamp(stat.st_mtime),
                    "content":       content,
                    "size":          len(content),
                })
            except Exception as e:
                print(f"Warning: could not read {md_file}: {e}")

        return methodologies

    # ── MOC scan ─────────────────────────────────────────────────────────────

    def scan_mocs(self) -> List[Dict]:
        mocs = []
        if not self.moc_dir.exists():
            return mocs

        for md_file in self.moc_dir.rglob("MOC-*.md"):
            try:
                content     = md_file.read_text(encoding="utf-8")
                frontmatter = self._extract_frontmatter(content)
                stat        = md_file.stat()
                mocs.append({
                    "path":          md_file,
                    "name":          md_file.stem,
                    "type":          frontmatter.get("type", "moc"),
                    "status":        frontmatter.get("status", "unknown"),
                    "created":       frontmatter.get("created", "unknown"),
                    "last_updated":  frontmatter.get("last-updated", "unknown"),
                    "last_modified": datetime.fromtimestamp(stat.st_mtime),
                    "dataview_count": content.count("```dataview"),
                    "link_count":    len(re.findall(r'\[\[([^\]]+)\]\]', content)),
                    "heading_count": len(re.findall(r'^#{1,3} [^\n]+', content, re.MULTILINE)),
                    "size":          len(content),
                    "content":       content,
                })
            except Exception as e:
                print(f"Warning: could not read MOC {md_file}: {e}")

        return mocs

    def check_moc_health(self, mocs: List[Dict]) -> Dict:
        health = {
            "total_mocs":       len(mocs),
            "with_dataview":    0,
            "with_frontmatter": 0,
            "active_mocs":      0,
            "stale_mocs":       [],
            "broken_links":     [],
            "low_link_density": [],
        }
        threshold = datetime.now() - timedelta(days=90)

        for moc in mocs:
            if moc["dataview_count"] > 0:
                health["with_dataview"] += 1
            if moc["type"] != "unknown":
                health["with_frontmatter"] += 1
            if moc["status"] == "active":
                health["active_mocs"] += 1
            if moc["last_modified"] < threshold:
                health["stale_mocs"].append({
                    "name":          moc["name"],
                    "last_modified": moc["last_modified"],
                    "days_ago":      (datetime.now() - moc["last_modified"]).days,
                })
            if moc["link_count"] < 5:
                health["low_link_density"].append({
                    "name":       moc["name"],
                    "link_count": moc["link_count"],
                })
            broken = self._detect_broken_links(moc["content"])
            if broken:
                health["broken_links"].append({"name": moc["name"], "broken": broken})

        return health

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _detect_broken_links(self, content: str) -> List[str]:
        broken = []
        if "[[]]" in content:
            broken.append("empty link")
        if content.count("[[") != content.count("]]"):
            broken.append("unclosed link")
        return broken

    def _extract_frontmatter(self, content: str) -> Dict:
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}
        fm = {}
        for line in match.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                fm[key.strip()] = value.strip()
        return fm

    def _extract_domain(self, file_path: Path, base_dir: Path) -> str:
        relative = file_path.relative_to(base_dir)
        return relative.parts[0] if len(relative.parts) > 1 else "Uncategorized"

    def detect_zombies(self, methodologies: List[Dict], days: int = 90) -> List[Dict]:
        threshold = datetime.now() - timedelta(days=days)
        return [
            {
                "name":          m["name"],
                "created":       m["created"],
                "last_modified": m["last_modified"],
                "days_ago":      (datetime.now() - m["last_modified"]).days,
            }
            for m in methodologies if m["last_modified"] < threshold
        ]

    def analyze_by_domain(self, methodologies: List[Dict]) -> Dict[str, List[Dict]]:
        domains: Dict[str, List[Dict]] = defaultdict(list)
        for m in methodologies:
            domains[m["domain"]].append(m)
        return dict(domains)

    # ── Report ────────────────────────────────────────────────────────────────

    def generate_full_report(self) -> str:
        methodologies = self.scan_methodologies()
        by_domain     = self.analyze_by_domain(methodologies)
        zombies       = self.detect_zombies(methodologies)
        mocs          = self.scan_mocs()
        moc_health    = self.check_moc_health(mocs)

        total_m  = len(methodologies) or 1
        total_mc = moc_health["total_mocs"] or 1

        report = f"""---
type: health-check-report
generated: {self.report_date}
---

# Knowledge Health Check Report v2.0

Generated: {self.report_date}

---

## 📊 Overview

### Methodology Library
- **Total methodologies**: {len(methodologies)}
- **Domains**: {len(by_domain)}
- **Zombie methodologies**: {len(zombies)} ({len(zombies)/total_m*100:.1f}%)

### MOC
- **Total MOCs**: {moc_health['total_mocs']}
- **Using Dataview**: {moc_health['with_dataview']} ({moc_health['with_dataview']/total_mc*100:.1f}%)
- **Complete frontmatter**: {moc_health['with_frontmatter']} ({moc_health['with_frontmatter']/total_mc*100:.1f}%)
- **Active MOCs**: {moc_health['active_mocs']}

---

## 🗺 MOC Health

| Metric | Count | % | Status |
|--------|-------|---|--------|
| Using Dataview | {moc_health['with_dataview']} | {moc_health['with_dataview']/total_mc*100:.1f}% | {'✅' if moc_health['with_dataview']/total_mc > 0.5 else '⚠️'} |
| Complete frontmatter | {moc_health['with_frontmatter']} | {moc_health['with_frontmatter']/total_mc*100:.1f}% | {'✅' if moc_health['with_frontmatter']/total_mc > 0.8 else '⚠️'} |
| Active status | {moc_health['active_mocs']} | {moc_health['active_mocs']/total_mc*100:.1f}% | {'✅' if moc_health['active_mocs']/total_mc > 0.7 else '⚠️'} |

**Stale MOCs (not updated in 90 days)**: {len(moc_health['stale_mocs'])}
"""
        if moc_health["stale_mocs"]:
            report += "\n| MOC | Last Modified | Days Ago |\n|-----|--------------|----------|\n"
            for m in sorted(moc_health["stale_mocs"], key=lambda x: x["days_ago"], reverse=True)[:10]:
                report += f"| {m['name']} | {m['last_modified'].strftime('%Y-%m-%d')} | {m['days_ago']} |\n"

        report += f"\n**Low link density (<5 links)**: {len(moc_health['low_link_density'])}\n"

        if moc_health["low_link_density"]:
            report += "\n| MOC | Links |\n|-----|-------|\n"
            for m in sorted(moc_health["low_link_density"], key=lambda x: x["link_count"])[:10]:
                report += f"| {m['name']} | {m['link_count']} |\n"

        report += f"\n**Broken links**: {len(moc_health['broken_links'])}\n"

        report += f"""
---

## 📚 Methodology Library

### By Domain

| Domain | Count | Zombies | Zombie % |
|--------|-------|---------|----------|
"""
        for domain, methods in sorted(by_domain.items(), key=lambda x: len(x[1]), reverse=True):
            dz = [z for z in zombies if any(m["name"] == z["name"] for m in methods)]
            report += f"| {domain} | {len(methods)} | {len(dz)} | {len(dz)/len(methods)*100:.1f}% |\n"

        report += f"""
### Zombie Methodologies (not modified in 90 days)

| Name | Domain | Created | Last Modified | Days Ago |
|------|--------|---------|---------------|----------|
"""
        for z in sorted(zombies, key=lambda x: x["days_ago"], reverse=True)[:20]:
            domain = next((m["domain"] for m in methodologies if m["name"] == z["name"]), "?")
            report += f"| {z['name']} | {domain} | {z['created']} | {z['last_modified'].strftime('%Y-%m-%d')} | {z['days_ago']} |\n"

        report += f"\n---\n\n*Generated by AI Tech Learn health check · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        return report


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("Usage: python health_check_v2.py <vault_path>")
        print('Example: python health_check_v2.py "/home/user/Obsidian Vault"')
        sys.exit(1)

    vault_path = sys.argv[1]
    print(f"=== Knowledge Health Check v2.0 ===")
    print(f"Vault: {vault_path}")

    checker = KnowledgeHealthCheckerV2(vault_path)
    report  = checker.generate_full_report()

    report_dir  = Path(vault_path) / Path(REPORT_FOLDER)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"_health-report-{checker.report_date}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"✅ Report saved: {report_path}")


if __name__ == "__main__":
    main()
