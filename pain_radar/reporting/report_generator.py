import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from pain_radar.storage.db import Database

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, db: Database, output_dir: Path, top_n: int = 15):
        self.db = db
        self.output_dir = output_dir
        self.top_n = top_n
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_reports(self) -> Dict[str, Path]:
        clusters = self.db.get_clusters_for_reporting(top_n=self.top_n)

        md_path = self.output_dir / "top-problems.md"
        csv_path = self.output_dir / "top-problems.csv"
        json_path = self.output_dir / "top-problems.json"

        self._generate_markdown(clusters, md_path)
        self._generate_csv(clusters, csv_path)
        self._generate_json(clusters, json_path)

        logger.info(f"Reports successfully written to {self.output_dir}")
        return {
            "markdown": md_path,
            "csv": csv_path,
            "json": json_path,
        }

    def _generate_markdown(self, clusters: List[Dict[str, Any]], out_path: Path) -> None:
        lines: List[str] = [
            "==================================================",
            "REDDIT PAIN RADAR",
            "==================================================",
            "",
        ]

        if not clusters:
            lines.append("No validated problem clusters with sufficient evidence found.")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return

        for idx, c in enumerate(clusters, 1):
            synth = c.get("synthesis") or {}
            target_user = synth.get("target_user") or c.get("target_user", "Unknown")
            workaround = synth.get("current_workaround") or "Manual ad-hoc processes"
            why_hurts = synth.get("why_it_hurts") or "Operational friction and wasted effort."

            workaround_pct = int(round(c.get("manual_workaround_rate", 0) * 100))
            failure_pct = int(round(c.get("existing_failure_rate", 0) * 100))
            purchase_pct = int(round(c.get("purchase_signal_rate", 0) * 100))

            lines.append(f"#{idx} {c.get('normalized_problem')}")
            lines.append("")
            lines.append(f"Pain Score: {int(round(c.get('pain_score', 0)))}/100")
            lines.append(f"Trend: {c.get('trend_label', 'NEW')}")
            lines.append(f"Mentions: {c.get('mention_count', 0)}")
            lines.append(f"Discussions: {c.get('unique_discussions', 0)}")
            lines.append(f"Subreddits: {c.get('unique_subreddits', 0)}")
            lines.append(f"Workaround Rate: {workaround_pct}%")
            lines.append(f"Existing Solution Failure: {failure_pct}%")
            lines.append(f"Purchase Signal: {purchase_pct}%")
            lines.append("")
            lines.append("TARGET USER")
            lines.append(target_user)
            lines.append("")
            lines.append("CURRENT WORKAROUND")
            lines.append(workaround)
            lines.append("")
            lines.append("WHY IT HURTS")
            lines.append(why_hurts)
            lines.append("")

            if synth.get("product_direction"):
                lines.append("OPPORTUNITY DIRECTION")
                lines.append(synth.get("product_direction"))
                lines.append("")

            evidence = c.get("evidence", [])
            lines.append("EVIDENCE")
            lines.append("")
            seen_urls = set()
            ev_count = 0
            for ev in evidence:
                u = ev.get("reddit_url")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    ev_count += 1
                    lines.append(f"{ev_count}. {u}")
                if ev_count >= 5:
                    break

            if not seen_urls:
                lines.append("No public evidence URLs recorded.")

            lines.append("")
            lines.append("--------------------------------------------------")
            lines.append("")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _generate_csv(self, clusters: List[Dict[str, Any]], out_path: Path) -> None:
        headers = [
            "rank",
            "cluster_id",
            "problem",
            "pain_score",
            "trend",
            "mentions",
            "discussions",
            "subreddits",
            "workaround_rate",
            "failure_rate",
            "purchase_signal_rate",
            "target_user",
            "current_workaround",
            "evidence_count",
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for idx, c in enumerate(clusters, 1):
                synth = c.get("synthesis") or {}
                writer.writerow([
                    idx,
                    c.get("cluster_id"),
                    c.get("normalized_problem"),
                    c.get("pain_score"),
                    c.get("trend_label"),
                    c.get("mention_count"),
                    c.get("unique_discussions"),
                    c.get("unique_subreddits"),
                    f"{int(round(c.get('manual_workaround_rate', 0) * 100))}%",
                    f"{int(round(c.get('existing_failure_rate', 0) * 100))}%",
                    f"{int(round(c.get('purchase_signal_rate', 0) * 100))}%",
                    synth.get("target_user") or c.get("target_user"),
                    synth.get("current_workaround") or "Manual methods",
                    len(c.get("evidence", [])),
                ])

    def _generate_json(self, clusters: List[Dict[str, Any]], out_path: Path) -> None:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(clusters, f, indent=2, ensure_ascii=False)
