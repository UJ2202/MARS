"""
Stage-specific helpers for the Industry News & Sentiment Pulse pipeline.

Stages:
  1 — Setup & Configuration (no AI — stores request + model config)
  2 — News Discovery & Collection (AI research via DDGS — headlines, raw data)
  3 — Deep Sentiment & Analysis (AI research via DDGS — analysis, trends, risks)
  4 — Final Report + PDF (AI compilation into 12-section report + PDF)

Each AI stage (2, 3, 4) supports HITL review between stages.
Model configuration follows the Deep Research pattern.
"""

import os
import re
import logging
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ─── Default model assignments per stage ─────────────────────────────────

DISCOVERY_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4o",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}

ANALYSIS_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4.1",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}

FINAL_REPORT_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4o",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}


TIME_WINDOW_LABELS = {
    "1d": "the past 24 hours",
    "7d": "the past week",
    "30d": "the past month",
    "90d": "the past 3 months",
    "2024": "the year 2024 (Jan–Dec 2024)",
    "2025": "the year 2025 (Jan–Dec 2025)",
    "2026": "the year 2026 (Jan–present 2026)",
    "2025-2026": "2025 through 2026",
    "Q1 2025": "Q1 2025 (Jan–Mar 2025)",
    "Q2 2025": "Q2 2025 (Apr–Jun 2025)",
    "Q3 2025": "Q3 2025 (Jul–Sep 2025)",
    "Q4 2025": "Q4 2025 (Oct–Dec 2025)",
    "Q1 2026": "Q1 2026 (Jan–Mar 2026)",
    "H1 2025": "first half of 2025 (Jan–Jun 2025)",
    "H2 2025": "second half of 2025 (Jul–Dec 2025)",
    "H1 2026": "first half of 2026 (Jan–Jun 2026)",
}


def _compute_year_scope(time_window: str) -> str:
    """Extract the target year(s) from a time_window value for search queries."""
    import re
    now = datetime.now()

    # If the time_window is a pure year like "2025", "2026"
    if re.match(r'^\d{4}$', time_window.strip()):
        return time_window.strip()

    # If it contains a year range like "2025-2026"
    m = re.match(r'^(\d{4})\s*[-–]\s*(\d{4})$', time_window.strip())
    if m:
        return f"{m.group(1)} {m.group(2)}"

    # If it contains a quarter like "Q1 2025"
    m = re.search(r'Q[1-4]\s*(\d{4})', time_window)
    if m:
        return m.group(1)

    # If it contains a half like "H1 2025"
    m = re.search(r'H[12]\s*(\d{4})', time_window)
    if m:
        return m.group(1)

    # Short codes: guess from current year
    if time_window in ("1d", "7d", "30d"):
        return str(now.year)
    if time_window == "90d":
        # Could span two years near Jan
        if now.month <= 3:
            return f"{now.year - 1} {now.year}"
        return str(now.year)

    # Fallback: extract any 4-digit year from the string
    years = re.findall(r'\b(20\d{2})\b', time_window)
    if years:
        return " ".join(sorted(set(years)))

    return str(now.year)


def _compute_exclusion_years(year_scope: str) -> str:
    """Build a human-readable list of years to exclude."""
    import re
    now = datetime.now()
    scope_years = set(re.findall(r'\b(20\d{2})\b', year_scope))
    scope_ints = {int(y) for y in scope_years} if scope_years else {now.year}

    # Build exclusion list: common years users might accidentally get
    all_recent = set(range(2020, now.year + 2))
    excluded = sorted(all_recent - scope_ints)
    if not excluded:
        return "years before 2024"
    return ", ".join(str(y) for y in excluded)


# ═══════════════════════════════════════════════════════════════════════════
# Stage 1 — Setup & Configuration (no AI)
# ═══════════════════════════════════════════════════════════════════════════

def build_user_input_output(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
) -> dict:
    """Build output_data for stage 1 (user input + config capture)."""
    return {
        "shared": {
            "industry": industry,
            "companies": companies or "",
            "region": region or "Global",
            "time_window": time_window or "7d",
            "user_input_summary": (
                f"Industry: {industry}\n"
                f"Companies: {companies or 'None specified'}\n"
                f"Region: {region or 'Global'}\n"
                f"Time Window: {time_window or '7d'}"
            ),
        },
        "artifacts": {},
        "chat_history": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2 — News Discovery & Collection (DDGS Research)
# ═══════════════════════════════════════════════════════════════════════════

def build_discovery_kwargs(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (news discovery)."""
    from cmbagent.task_framework.prompts.newspulse.discovery import (
        discovery_planner_prompt,
        discovery_researcher_prompt,
    )
    from cmbagent.task_framework.utils import create_work_dir

    cfg = {**DISCOVERY_DEFAULTS, **(config_overrides or {})}
    discovery_dir = create_work_dir(work_dir, "discovery")
    time_window_human = TIME_WINDOW_LABELS.get(time_window, time_window)
    year_scope = _compute_year_scope(time_window)
    exclusion_years = _compute_exclusion_years(year_scope)

    task_desc = (
        f"Search and collect the latest news, breaking stories, and major "
        f"developments in the {industry} industry for the {region} region "
        f"over {time_window_human} (year: {year_scope}). Use web search "
        f"extensively to gather real, current data from multiple sources. "
        f"IMPORTANT: Every search query must include '{year_scope}' and '{region}'. "
        f"Discard any result from {exclusion_years}."
    )
    if companies:
        task_desc += f" Include focused searches on: {companies}."

    fmt_kwargs = dict(
        industry=industry,
        company=companies or "None specified",
        companies=companies or "None specified",
        region=region,
        time_window=time_window,
        time_window_human=time_window_human,
        year_scope=year_scope,
        exclusion_years=exclusion_years,
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=6,
        max_n_attempts=6,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=discovery_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=discovery_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(discovery_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="news_discovery",
        callbacks=callbacks,
    )


def extract_stage_result(results: dict) -> str:
    """Extract the report content from chat_history (shared by stages 2/3/4)."""
    from cmbagent.task_framework.utils import get_task_result, extract_clean_markdown

    chat_history = results["chat_history"]

    task_result = ""
    for agent_name in ("researcher", "researcher_response_formatter"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: pick longest non-empty message
    if not task_result:
        logger.warning("Primary extraction failed, scanning all messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best

    if not task_result:
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        raise ValueError(
            f"No report content found in chat history. Available agents: {list(set(agent_names))}"
        )

    return extract_clean_markdown(task_result)


def save_stage_file(content: str, work_dir: str, filename: str) -> str:
    """Write a stage output file to input_files/ and return the path."""
    input_dir = os.path.join(str(work_dir), "input_files")
    os.makedirs(input_dir, exist_ok=True)
    path = os.path.join(input_dir, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def build_discovery_output(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    news_collection: str,
    file_path: str,
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (news discovery stage)."""
    return {
        "shared": {
            "industry": industry,
            "companies": companies,
            "region": region,
            "time_window": time_window,
            "news_collection": news_collection,
        },
        "artifacts": {
            "news_collection.md": file_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Deep Sentiment & Analysis (DDGS Research)
# ═══════════════════════════════════════════════════════════════════════════

def build_analysis_kwargs(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    news_collection: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (deep analysis)."""
    from cmbagent.task_framework.prompts.newspulse.analysis import (
        analysis_planner_prompt,
        analysis_researcher_prompt,
    )
    from cmbagent.task_framework.utils import create_work_dir

    cfg = {**ANALYSIS_DEFAULTS, **(config_overrides or {})}
    analysis_dir = create_work_dir(work_dir, "analysis")
    time_window_human = TIME_WINDOW_LABELS.get(time_window, time_window)
    year_scope = _compute_year_scope(time_window)
    exclusion_years = _compute_exclusion_years(year_scope)

    task_desc = (
        f"Perform deep sentiment analysis, trend identification, risk assessment, "
        f"and company analysis for the {industry} industry in {region} "
        f"during {time_window_human} ({year_scope}). "
        f"Build on the collected news data and perform additional web searches "
        f"to create comprehensive analytical insights. "
        f"IMPORTANT: Every search query must include '{year_scope}' and '{region}'. "
        f"Discard any data from {exclusion_years}."
    )
    if companies:
        task_desc += f" Provide detailed analysis for: {companies}."

    fmt_kwargs = dict(
        industry=industry,
        company=companies or "None specified",
        companies=companies or "None specified",
        region=region,
        time_window=time_window,
        time_window_human=time_window_human,
        year_scope=year_scope,
        exclusion_years=exclusion_years,
        news_collection=news_collection,
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=8,
        max_n_attempts=6,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=analysis_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=analysis_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(analysis_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="deep_analysis",
        callbacks=callbacks,
    )


def build_analysis_output(
    shared_state: dict,
    deep_analysis: str,
    file_path: str,
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (deep analysis stage)."""
    return {
        "shared": {
            **shared_state,
            "deep_analysis": deep_analysis,
        },
        "artifacts": {
            "deep_analysis.md": file_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4 — Final Report + PDF Build
# ═══════════════════════════════════════════════════════════════════════════

def build_final_report_kwargs(
    industry: str,
    companies: str,
    region: str,
    time_window: str,
    news_collection: str,
    deep_analysis: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (final report)."""
    from cmbagent.task_framework.prompts.newspulse.final_report import (
        final_report_planner_prompt,
        final_report_researcher_prompt,
    )
    from cmbagent.task_framework.utils import create_work_dir

    cfg = {**FINAL_REPORT_DEFAULTS, **(config_overrides or {})}
    final_dir = create_work_dir(work_dir, "final_report")
    time_window_human = TIME_WINDOW_LABELS.get(time_window, time_window)
    year_scope = _compute_year_scope(time_window)
    exclusion_years = _compute_exclusion_years(year_scope)

    task_desc = (
        f"Produce the final executive Industry News & Sentiment Pulse report "
        f"for the {industry} industry in {region} over {time_window_human} "
        f"({year_scope}). Compile all research and analysis into a polished, "
        f"publication-ready report with standardized sections. "
        f"All data must be from {year_scope} and focused on {region}. "
        f"Perform final verification searches (include '{year_scope} {region}' in queries)."
    )

    fmt_kwargs = dict(
        industry=industry,
        company=companies or "None specified",
        companies=companies or "None specified",
        region=region,
        time_window=time_window,
        time_window_human=time_window_human,
        year_scope=year_scope,
        exclusion_years=exclusion_years,
        news_collection=news_collection,
        deep_analysis=deep_analysis,
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=6,
        max_n_attempts=6,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=final_report_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=final_report_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(final_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="final_report",
        callbacks=callbacks,
    )


def build_final_report_output(
    shared_state: dict,
    final_report: str,
    final_report_path: str,
    pdf_path: Optional[str],
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (final report stage)."""
    artifacts = {"final_report.md": final_report_path}
    if pdf_path:
        artifacts["report.pdf"] = pdf_path

    return {
        "shared": {
            **shared_state,
            "final_report": final_report,
        },
        "artifacts": artifacts,
        "chat_history": chat_history,
    }


def generate_pdf_from_markdown(markdown_content: str, work_dir: str, industry: str) -> Optional[str]:
    """Convert a markdown report to PDF.

    Uses markdown → HTML → PDF conversion via weasyprint (if available),
    falls back to a simple text-based approach.
    """
    output_dir = os.path.join(str(work_dir), "output")
    os.makedirs(output_dir, exist_ok=True)

    safe_name = re.sub(r'[^\w\s-]', '', industry).strip().replace(' ', '_')
    pdf_filename = f"news_sentiment_pulse_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)

    try:
        from weasyprint import HTML
        html_content = _markdown_to_html(markdown_content, industry)
        HTML(string=html_content).write_pdf(pdf_path)
        logger.info("PDF generated via weasyprint: %s", pdf_path)
        return pdf_path
    except ImportError:
        logger.info("weasyprint not available, trying fpdf2")

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, f"Industry News & Sentiment Pulse", ln=True, align="C")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, industry, ln=True, align="C")
        pdf.cell(0, 6, datetime.now().strftime("%B %d, %Y"), ln=True, align="C")
        pdf.ln(10)

        # Body
        for line in markdown_content.split('\n'):
            line = line.rstrip()
            if line.startswith('# '):
                pdf.set_font("Helvetica", "B", 16)
                pdf.ln(6)
                pdf.multi_cell(0, 8, line[2:])
            elif line.startswith('## '):
                pdf.set_font("Helvetica", "B", 14)
                pdf.ln(4)
                pdf.multi_cell(0, 7, line[3:])
            elif line.startswith('### '):
                pdf.set_font("Helvetica", "B", 12)
                pdf.ln(3)
                pdf.multi_cell(0, 6, line[4:])
            elif line.startswith('- ') or line.startswith('* '):
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, f"  \u2022 {line[2:]}")
            elif line.startswith('|'):
                pdf.set_font("Courier", "", 9)
                pdf.multi_cell(0, 4, line)
            elif line.strip() == '---':
                pdf.ln(3)
                pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
                pdf.ln(3)
            elif line.strip():
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, line)
            else:
                pdf.ln(3)

        pdf.output(pdf_path)
        logger.info("PDF generated via fpdf2: %s", pdf_path)
        return pdf_path
    except ImportError:
        logger.warning("Neither weasyprint nor fpdf2 available for PDF generation")
        return None


def _markdown_to_html(markdown_content: str, industry: str) -> str:
    """Convert markdown to styled HTML for PDF rendering."""
    try:
        import markdown
        body = markdown.markdown(
            markdown_content,
            extensions=['tables', 'fenced_code'],
        )
    except ImportError:
        # Fallback: basic conversion
        import html
        body = f"<pre>{html.escape(markdown_content)}</pre>"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    margin: 2cm 2.5cm;
    @top-center {{
      content: "{industry} — Industry News & Sentiment Pulse";
      font-size: 8pt;
      color: #888;
    }}
    @bottom-center {{
      content: "Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #888;
    }}
  }}
  body {{
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: #1a1a2e;
    max-width: 780px;
    margin: 0 auto;
  }}
  h1 {{
    color: #0a1628;
    border-bottom: 3px solid #0f3460;
    padding-bottom: 10px;
    font-size: 24pt;
    letter-spacing: -0.5px;
    margin-top: 0;
  }}
  h2 {{
    color: #0f3460;
    border-bottom: 2px solid #e8edf3;
    padding-bottom: 6px;
    margin-top: 28px;
    font-size: 16pt;
    letter-spacing: -0.3px;
    page-break-after: avoid;
  }}
  h3 {{
    color: #533483;
    margin-top: 18px;
    font-size: 13pt;
    page-break-after: avoid;
  }}
  h4 {{
    color: #2d4a7a;
    margin-top: 14px;
    font-size: 11pt;
    page-break-after: avoid;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 14px 0;
    font-size: 10pt;
  }}
  th, td {{
    border: 1px solid #d1d5db;
    padding: 10px 14px;
    text-align: left;
  }}
  th {{
    background: linear-gradient(135deg, #0f3460, #1a5276);
    color: white;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 9pt;
    letter-spacing: 0.5px;
  }}
  tr:nth-child(even) {{ background-color: #f8f9fb; }}
  tr:hover {{ background-color: #eef2f7; }}
  ul, ol {{ margin: 10px 0; padding-left: 24px; }}
  li {{ margin-bottom: 6px; }}
  hr {{
    border: none;
    border-top: 2px solid #e8edf3;
    margin: 24px 0;
  }}
  blockquote {{
    border-left: 4px solid #0f3460;
    margin: 16px 0;
    padding: 12px 20px;
    background-color: #f8f9fb;
    color: #374151;
    font-style: italic;
    font-size: 10pt;
  }}
  strong {{ color: #1a1a2e; }}
  a {{ color: #0f3460; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .header {{
    text-align: center;
    margin-bottom: 36px;
    padding: 28px 24px;
    background: linear-gradient(135deg, #0a1628 0%, #0f3460 50%, #533483 100%);
    color: white;
    border-radius: 8px;
  }}
  .header h1 {{
    color: white;
    border: none;
    margin: 0 0 8px 0;
    font-size: 26pt;
  }}
  .header .subtitle {{
    font-size: 14pt;
    color: #e0e0e0;
    margin: 4px 0;
    font-weight: 300;
  }}
  .header .meta {{
    font-size: 10pt;
    color: #b0c4de;
    margin-top: 12px;
    letter-spacing: 0.5px;
  }}
  .footer {{
    margin-top: 48px;
    padding-top: 16px;
    border-top: 2px solid #e8edf3;
    text-align: center;
    font-size: 8.5pt;
    color: #888;
  }}
  .footer .brand {{
    font-weight: 600;
    color: #0f3460;
    font-size: 9pt;
  }}
</style>
</head>
<body>
<div class="header">
  <h1>Industry News &amp; Sentiment Pulse</h1>
  <div class="subtitle">{industry} — Executive Intelligence Report</div>
  <div class="meta">{datetime.now().strftime('%B %d, %Y')} &middot; Powered by MARS AI</div>
</div>
{body}
<div class="footer">
  <div class="brand">MARS AI Research Platform</div>
  Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
  &middot; All information sourced from publicly available data
  &middot; Verify independently before making business decisions
</div>
</body>
</html>"""
