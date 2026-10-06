import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional
from cerebras.cloud.sdk import Cerebras
from pain_radar.config import AppConfig

logger = logging.getLogger(__name__)


class CerebrasClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.mock_mode = config.mock_mode
        self._client: Optional[Cerebras] = None

        if not self.mock_mode:
            self._init_client()

    def _init_client(self) -> None:
        api_key = self.config.cerebras_api_key
        if not api_key:
            logger.warning("CEREBRAS_API_KEY not found. Operating in mock/test mode.")
            self.mock_mode = True
            return

        try:
            self._client = Cerebras(
                api_key=api_key,
                timeout=self.config.cerebras_timeout,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Cerebras client: {e}")
            raise

    def check_connection(self) -> bool:
        """
        Validates API key and model availability.
        """
        if self.mock_mode:
            logger.info("Running in mock mode; connection check bypassed.")
            return True

        if not self._client:
            raise ValueError("Cerebras client is not initialized.")

        try:
            # Simple minimal ping
            resp = self._client.chat.completions.create(
                model=self.config.cerebras_model,
                messages=[{"role": "user", "content": "Respond with OK"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.error(f"Cerebras API connection failed for model '{self.config.cerebras_model}': {e}")
            raise

    def generate_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Call Cerebras chat completion with exponential backoff and rate limit handling.
        """
        if self.mock_mode or not self._client:
            return self._mock_completion(user_prompt)

        temp = temperature if temperature is not None else self.config.cerebras_temperature
        tokens = max_tokens if max_tokens is not None else self.config.cerebras_max_tokens

        retries = 0
        backoff = 1.0

        while retries <= self.config.cerebras_max_retries:
            try:
                response = self._client.chat.completions.create(
                    model=self.config.cerebras_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                    max_tokens=tokens,
                    response_format={"type": "json_object"},
                )
                choice = response.choices[0]
                return choice.message.content or ""
            except Exception as e:
                err_str = str(e).lower()
                retries += 1
                if "rate limit" in err_str or "429" in err_str:
                    logger.warning(f"Rate limited by Cerebras API. Backing off {backoff:.1f}s (retry {retries})...")
                    time.sleep(backoff)
                    backoff *= 2.0
                elif retries > self.config.cerebras_max_retries:
                    logger.error(f"Cerebras API call failed after {retries} retries: {e}")
                    raise
                else:
                    logger.warning(f"Cerebras API request failed: {e}. Retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                    backoff *= 1.5

        raise RuntimeError("Exceeded maximum retries for Cerebras API call.")

    def _mock_completion(self, user_prompt: str) -> str:
        """
        Deterministic mock generator for offline development and testing.
        """
        lower = user_prompt.lower()
        if "reconcil" in lower or "invoice" in lower or "quickbooks" in lower:
            return json.dumps({
                "is_real_problem": True,
                "pain_level": 4,
                "recurring_problem": True,
                "manual_workaround": True,
                "existing_solution_failure": True,
                "purchase_signal": False,
                "switching_signal": True,
                "problem_type": "manual_work",
                "problem_statement": "Small businesses manually reconcile invoices and payments across banking and accounting tools.",
                "target_user": "Small business owners & bookkeepers",
                "current_workaround": "Manual Excel exports and line-by-line spreadsheet matching every Friday",
                "why_painful": "Takes hours each week and causes billing reconciliation errors and delay in closing books",
                "confidence": 0.92
            })
        elif "approval" in lower or "client" in lower or "whatsapp" in lower:
            return json.dumps({
                "is_real_problem": True,
                "pain_level": 4,
                "recurring_problem": True,
                "manual_workaround": True,
                "existing_solution_failure": False,
                "purchase_signal": True,
                "switching_signal": False,
                "problem_type": "workflow_friction",
                "problem_statement": "Web development agencies manually chase client approvals across scattered WhatsApp and email threads because current portals lack external sign-off links.",
                "target_user": "Design and marketing agencies",
                "current_workaround": "Scattered WhatsApp messages, email threads, and manual spreadsheet reminders",
                "why_painful": "Delayed client approvals block sprint work and lead to scope creep without accountability",
                "confidence": 0.88
            })
        elif "how did you get" in lower or "first 100 users" in lower:
            return json.dumps({
                "is_real_problem": False,
                "pain_level": 1,
                "recurring_problem": False,
                "manual_workaround": False,
                "existing_solution_failure": False,
                "purchase_signal": False,
                "switching_signal": False,
                "problem_type": "other",
                "problem_statement": "Early-stage founders seek actionable distribution playbooks when standard launch channels yield zero initial user traction.",
                "target_user": "Early-stage founders",
                "current_workaround": "None specified",
                "why_painful": "Low pain discussion seeking inspirational advice",
                "confidence": 0.85
            })
        else:
            return json.dumps({
                "is_real_problem": True,
                "pain_level": 3,
                "recurring_problem": True,
                "manual_workaround": True,
                "existing_solution_failure": False,
                "purchase_signal": False,
                "switching_signal": False,
                "problem_type": "time_waste",
                "problem_statement": "Early-stage SaaS founders manually combine prospect research, email discovery, personalization and Gmail to run cold outreach.",
                "target_user": "Early-stage SaaS founders",
                "current_workaround": "Custom manual spreadsheets and ad-hoc scripts",
                "why_painful": "Consumes valuable development and operational bandwidth",
                "confidence": 0.80
            })
