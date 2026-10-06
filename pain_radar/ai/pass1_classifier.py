import concurrent.futures
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pain_radar.ai.cerebras_client import CerebrasClient
from pain_radar.ai.schemas import PainSignalSchema
from pain_radar.storage.db import Database
from pain_radar.storage.models import PainSignalRecord

logger = logging.getLogger(__name__)

PASS1_SYSTEM_PROMPT = """You are an objective, evidence-backed problem discovery engine analyzing real Reddit posts and comments.
Your goal is NOT to brainstorm startup ideas or invent hypothetical solutions.
Your mission is to rigorously evaluate whether the text describes a REAL, REPEATED, PAINFUL PROBLEM experienced by an actual person.

STRONG SIGNALS:
- "I spend 3 hours every week doing this manually"
- "I have tried 5 tools and none work"
- "My software costs $500/month and still doesn't solve this"
- "Every Friday I have to export this to Excel"
- "Does anyone know a better way to handle this?"
- "I keep having to do this repetitive workaround"

WEAK SIGNALS (NOT REAL PAIN):
- "Someone should build an app for this"
- "It would be cool if..."
- "I have an idea..."
- "Wouldn't it be nice if..."

OUTPUT FORMAT:
Respond with a SINGLE, RAW, VALID JSON object matching this exact schema:
{
  "is_real_problem": true,
  "pain_level": 1,
  "recurring_problem": true,
  "manual_workaround": true,
  "existing_solution_failure": false,
  "purchase_signal": false,
  "switching_signal": false,
  "problem_type": "manual_work",
  "problem_statement": "A concise, objective 1-sentence statement of the underlying problem.",
  "target_user": "Specific persona (e.g. 'Small agency owners', 'E-commerce store managers')",
  "current_workaround": "The specific manual method, tool combination, or process they use today",
  "why_painful": "Concrete reasons (wasted hours, financial loss, high churn, errors)",
  "confidence": 0.90
}

Valid pain_level values: 1 (trivial), 2 (minor), 3 (moderate), 4 (significant), 5 (severe).
Valid problem_type values: "manual_work", "workflow_friction", "bad_existing_tool", "expensive_solution", "missing_solution", "unreliable_solution", "repetitive_task", "time_waste", "other".
Do NOT output markdown code blocks (```json) or introductory commentary. Output only JSON.
"""

REPAIR_SYSTEM_PROMPT = """You are a JSON repair tool. You take raw text or broken JSON and output ONLY a single valid JSON object strictly matching the required schema. No commentary, no code fences.
Required fields: is_real_problem (bool), pain_level (int 1-5), recurring_problem (bool), manual_workaround (bool), existing_solution_failure (bool), purchase_signal (bool), switching_signal (bool), problem_type (str), problem_statement (str), target_user (str), current_workaround (str), why_painful (str), confidence (float 0-1).
"""


class Pass1Classifier:
    def __init__(self, db: Database, client: CerebrasClient, concurrency: int = 4):
        self.db = db
        self.client = client
        self.concurrency = concurrency

    def _parse_and_validate(self, raw_text: str) -> Optional[PainSignalSchema]:
        # Try direct parse
        try:
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            data = json.loads(cleaned)
            return PainSignalSchema.model_validate(data)
        except Exception:
            pass

        # Attempt repair call
        try:
            repair_raw = self.client.generate_chat_completion(
                system_prompt=REPAIR_SYSTEM_PROMPT,
                user_prompt=f"Fix and format this JSON:\n{raw_text}",
                temperature=0.0,
            )
            cleaned = repair_raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            data = json.loads(cleaned)
            return PainSignalSchema.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to repair/validate LLM response: {e}")
            return None

    def classify_single(self, candidate: Dict[str, Any]) -> Optional[PainSignalRecord]:
        user_prompt = f"REDDIT POST FROM r/{candidate['subreddit']}:\n\n{candidate['full_context']}"

        try:
            raw_response = self.client.generate_chat_completion(
                system_prompt=PASS1_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            schema = self._parse_and_validate(raw_response)
            if not schema:
                return None

            signal = PainSignalRecord(
                signal_id=f"sig_{uuid.uuid4().hex[:12]}",
                post_id=candidate["post_id"],
                subreddit=candidate["subreddit"],
                reddit_url=candidate["reddit_url"],
                is_real_problem=schema.is_real_problem,
                pain_level=schema.pain_level,
                recurring_problem=schema.recurring_problem,
                manual_workaround=schema.manual_workaround,
                existing_solution_failure=schema.existing_solution_failure,
                purchase_signal=schema.purchase_signal,
                switching_signal=schema.switching_signal,
                problem_type=schema.problem_type,
                problem_statement=schema.problem_statement,
                target_user=schema.target_user,
                current_workaround=schema.current_workaround,
                why_painful=schema.why_painful,
                confidence=schema.confidence,
                original_text=candidate["full_context"][:1000],
            )
            return signal
        except Exception as e:
            logger.error(f"Error classifying post {candidate.get('post_id')}: {e}")
            return None

    def classify_batch(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_candidates = len(candidates)
        real_problems_count = 0
        failed_count = 0

        logger.info(f"=== Starting PASS 1 Analysis: {total_candidates} candidates (Concurrency: {self.concurrency}) ===")

        signals: List[PainSignalRecord] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_cand = {executor.submit(self.classify_single, c): c for c in candidates}

            for idx, future in enumerate(concurrent.futures.as_completed(future_to_cand)):
                sig = future.result()
                if sig:
                    self.db.save_pain_signal(sig)
                    signals.append(sig)
                    if sig.is_real_problem:
                        real_problems_count += 1
                else:
                    failed_count += 1

                if (idx + 1) % 10 == 0 or (idx + 1) == total_candidates:
                    logger.info(
                        f"Analyzed {idx + 1}/{total_candidates} candidates | Real problems: {real_problems_count} | Failed/Skipped: {failed_count}"
                    )

        logger.info(f"=== PASS 1 Completed: {real_problems_count} real pain signals extracted ===")
        return {
            "total_candidates": total_candidates,
            "real_problems": real_problems_count,
            "failed_extractions": failed_count,
        }
