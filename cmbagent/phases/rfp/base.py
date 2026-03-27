"""
Shared base for all RFP proposal generator phases.

Provides the common `_run_llm_stage` helper that every RFP phase calls.
Each phase subclass only needs to supply:
  - phase_type / display_name
  - a system prompt & user prompt builder
  - which shared-state keys it reads and writes
"""

import os
import time
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus

logger = logging.getLogger(__name__)


@dataclass
class RfpPhaseConfig(PhaseConfig):
    """Shared config knobs for every RFP stage."""
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_completion_tokens: int = 16384
    # Multi-turn: number of self-review iterations the LLM can do.
    # 0 = single-shot, 1+ = generate → review → refine loop.
    n_reviews: int = 1
    review_model: Optional[str] = None  # defaults to same as model


class RfpPhaseBase(Phase):
    """
    Abstract helper that runs a two-pass generate→review cycle.

    Subclasses implement:
        build_user_prompt(context) -> str
        system_prompt -> str (property)
        shared_output_key -> str (property)
        output_filename -> str | None (property)
    """

    config: RfpPhaseConfig

    def __init__(self, config: RfpPhaseConfig = None):
        super().__init__(config)
        self.config: RfpPhaseConfig = config or RfpPhaseConfig(phase_type=self.phase_type)

    # ---- subclass hooks ----

    @property
    def system_prompt(self) -> str:
        """System-level instruction for the generation pass."""
        return (
            "You are a world-class technical proposal consultant. "
            "Produce detailed, professional, well-structured markdown documents."
        )

    @property
    def review_system_prompt(self) -> str:
        """System-level instruction for the review pass."""
        return (
            "You are a senior proposal reviewer at a top-tier consulting firm.  "
            "You will be given a draft document and must improve it to professional "
            "submission quality.  Specifically:\n"
            "1. Fix factual errors, strengthen weak sections, add missing detail\n"
            "2. Improve structure and flow, ensure proper section numbering\n"
            "3. Ensure ALL cost figures are present, consistent, and fit within any stated budget\n"
            "4. Verify every tool/technology has a comparison table vs alternatives with clear justification\n"
            "5. Verify security features are compared for each major tool and service\n"
            "6. Verify cloud provider comparison and justification sections are thorough\n"
            "7. Add professional tables where data is listed as bullets\n"
            "8. CRITICAL: Replace ANY placeholder text like '[Insert ...]', '[To be added]', "
            "'[Insert detailed cost tables]', '[Insert glossary]', or any bracket-enclosed "
            "placeholder with ACTUAL content derived from the document's own data.  "
            "Zero placeholders are acceptable in a final document.\n"
            "9. Ensure ALL monetary values are in USD ($) only — no INR, EUR, GBP, or mixed currencies\n"
            "10. Verify every cost table has both Monthly and Annual columns with actual dollar figures in every cell — no empty cells\n"
            "11. Verify Annual Cost = Monthly Cost × 12 (fix any math errors)\n"
            "12. If the document has appendices, verify they contain REAL content (full tables, glossary entries, references) — not brief descriptions\n"
            "13. Ensure the document reads as a polished enterprise proposal — not an AI summary\n"
            "Return ONLY the improved markdown, no commentary."
        )

    @property
    def shared_output_key(self) -> str:  # pragma: no cover
        raise NotImplementedError

    @property
    def output_filename(self) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError

    def build_user_prompt(self, context: PhaseContext) -> str:  # pragma: no cover
        raise NotImplementedError

    # ---- execution ----

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """Run generate pass, then optional review pass(es)."""
        from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider

        self._status = PhaseStatus.RUNNING
        start = time.time()

        try:
            client = create_openai_client(timeout=300)
            model = self.config.model
            resolved = resolve_model_for_provider(model)
            review_model = resolve_model_for_provider(self.config.review_model or model)

            # Reasoning models (o3-*, o1-*) do not support the temperature param
            _is_reasoning = any(model.startswith(p) for p in ("o3", "o1"))
            _is_review_reasoning = any((self.config.review_model or model).startswith(p) for p in ("o3", "o1"))

            user_prompt = self.build_user_prompt(context)

            # --- generation pass ---
            print(f"[{self.display_name}] Sending generation request to {model}...")
            def _gen():
                params: dict = {
                    "model": resolved,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_completion_tokens": self.config.max_completion_tokens,
                }
                if not _is_reasoning:
                    params["temperature"] = self.config.temperature
                return client.chat.completions.create(**params)

            gen_resp = await asyncio.to_thread(_gen)
            content = gen_resp.choices[0].message.content or ""
            print(f"[{self.display_name}] Generation complete ({len(content)} chars)")

            total_prompt = (gen_resp.usage.prompt_tokens if gen_resp.usage else 0)
            total_completion = (gen_resp.usage.completion_tokens if gen_resp.usage else 0)

            # --- review passes ---
            for i in range(self.config.n_reviews):
                print(f"[{self.display_name}] Running review pass {i + 1}/{self.config.n_reviews}...")
                def _review(draft=content):
                    params: dict = {
                        "model": review_model,
                        "messages": [
                            {"role": "system", "content": self.review_system_prompt},
                            {"role": "user", "content": f"Draft document:\n\n{draft}"},
                        ],
                        "max_completion_tokens": self.config.max_completion_tokens,
                    }
                    if not _is_review_reasoning:
                        params["temperature"] = self.config.temperature
                    return client.chat.completions.create(**params)

                rev_resp = await asyncio.to_thread(_review)
                content = rev_resp.choices[0].message.content or content
                print(f"[{self.display_name}] Review pass complete ({len(content)} chars)")
                total_prompt += (rev_resp.usage.prompt_tokens if rev_resp.usage else 0)
                total_completion += (rev_resp.usage.completion_tokens if rev_resp.usage else 0)

            # --- save to disk ---
            if self.output_filename:
                out_dir = os.path.join(context.work_dir, "input_files")
                os.makedirs(out_dir, exist_ok=True)
                fpath = os.path.join(out_dir, self.output_filename)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

            # --- build output ---
            duration = time.time() - start
            context.output_data = {
                "shared": {self.shared_output_key: content},
                "artifacts": {"model": model},
                "cost": {
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "total_tokens": total_prompt + total_completion,
                },
            }
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                timing={"total": duration},
            )

        except Exception as exc:
            self._status = PhaseStatus.FAILED
            logger.error("RFP phase %s failed: %s", self.phase_type, exc, exc_info=True)
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(exc),
            )

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if not context.task:
            errors.append("task (RFP content) is required")
        return errors
