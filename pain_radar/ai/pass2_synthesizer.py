import json
import logging
import re
from typing import Any, Dict, List, Optional

from pain_radar.ai.cerebras_client import CerebrasClient
from pain_radar.ai.schemas import OpportunitySynthesisSchema
from pain_radar.storage.db import Database

logger = logging.getLogger(__name__)

PASS2_SYSTEM_PROMPT = """You are an evidence-grounded product discovery analyst.
You synthesize problem clusters derived from real user discussions on Reddit.

STRICT RULES:
1. Do NOT invent hypothetical competitors, market valuations, or unsourced claims.
2. Ground all insights directly on the provided user evidence snippets.
3. Clearly distinguish observed user behavior from product hypotheses.
4. Output ONLY a valid JSON object matching this exact schema:

{
  "problem_summary": "Clear, grounded synthesis of the recurring friction.",
  "target_user": "Persona consistently reflected in the quotes.",
  "why_it_hurts": "Root cause of the pain and operational impact.",
  "current_workaround": "Actual workarounds and manual processes used by commenters.",
  "existing_solutions": ["Names of specific tools/software mentioned in quotes, if any"],
  "observed_gaps": ["Specific shortcomings of current tools mentioned in quotes"],
  "product_direction": "High-leverage, practical product approach to eliminate this friction.",
  "risks": ["Realistic adoption, workflow, or technical risks"]
}

Do NOT wrap the output in markdown codeblocks (```json). Output pure JSON only.
"""


class Pass2Synthesizer:
    def __init__(self, db: Database, client: CerebrasClient):
        self.db = db
        self.client = client

    def synthesize_cluster(self, cluster_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        evidence = cluster_data.get("evidence", [])
        evidence_snippets = []
        for idx, ev in enumerate(evidence[:6]):
            evidence_snippets.append(
                f"Evidence #{idx+1} [Subreddit: r/{ev.get('subreddit')}, URL: {ev.get('reddit_url')}]:\n\"{ev.get('original_text', '')}\""
            )

        context = f"""PROBLEM CLUSTER:
- Normalized Problem: {cluster_data.get('normalized_problem')}
- Identified Target User: {cluster_data.get('target_user')}
- Mention Count: {cluster_data.get('mention_count')}
- Unique Discussions: {cluster_data.get('unique_discussions')}
- Workaround Rate: {int(cluster_data.get('manual_workaround_rate', 0) * 100)}%
- Tool Failure Rate: {int(cluster_data.get('existing_failure_rate', 0) * 100)}%

EVIDENCE SNIPPETS:
{chr(10).join(evidence_snippets)}
"""

        try:
            if self.client.mock_mode:
                synth = {
                    "problem_summary": cluster_data.get("normalized_problem"),
                    "target_user": cluster_data.get("target_user"),
                    "why_it_hurts": "Repetitive manual friction consuming critical working hours and causing operational errors.",
                    "current_workaround": "Spreadsheets, manual copy-pasting, and ad-hoc chat channels.",
                    "existing_solutions": ["Generic spreadsheets", "Fragmented point solutions"],
                    "observed_gaps": ["Lack of native workflow integration and automation."],
                    "product_direction": "A focused, streamlined utility specifically automating this recurring handoff.",
                    "risks": ["User inertia with existing free spreadsheets."],
                }
            else:
                raw_res = self.client.generate_chat_completion(
                    system_prompt=PASS2_SYSTEM_PROMPT,
                    user_prompt=context,
                    temperature=0.2,
                    max_tokens=3000,
                )
                match = re.search(r"\{.*\}", raw_res, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    parsed = json.loads(json_str)
                else:
                    cleaned = raw_res.strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.strip("`")
                        if cleaned.startswith("json"):
                            cleaned = cleaned[4:].strip()
                    parsed = json.loads(cleaned)

                validated = OpportunitySynthesisSchema.model_validate(parsed)
                synth = validated.model_dump()

            self.db.update_cluster_synthesis(cluster_data["cluster_id"], synth)
            return synth
        except Exception as e:
            logger.warning(f"Failed to synthesize cluster {cluster_data.get('cluster_id')}: {e}")
            return None

    def synthesize_top_clusters(self, top_n: int = 10) -> None:
        logger.info(f"=== Starting PASS 2 Synthesis for top {top_n} clusters ===")
        clusters = self.db.get_clusters_for_reporting(top_n=top_n)

        for idx, c in enumerate(clusters):
            logger.info(f"Synthesizing #{idx+1}: {c.get('normalized_problem')[:60]}...")
            self.synthesize_cluster(c)

        logger.info("=== PASS 2 Synthesis Completed ===")
