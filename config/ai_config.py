"""AI configuration — Gemini API integration.

Feature is intentionally hidden: the Executive Dashboard will only show
the AI Brief expander when GEMINI_API_KEY is set as an environment variable.
If the key is absent or the API call fails, the feature is silently absent.
"""
import os


def is_ai_enabled() -> bool:
    """Return True only if a Gemini API key is configured."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def generate_executive_brief(scenario_summary: dict) -> str:
    """Call Gemini and return a 3-paragraph plain-English executive brief.

    Args:
        scenario_summary: dict with keys:
            scenario_name, scenario_type, horizon, total_supply, total_demand,
            net_gap, units_at_risk, red_count, amber_count, total_rto_need,
            potential_saving, top_risk_unit, top_risk_gap, top_opportunity

    Returns:
        Generated text, or empty string on any error.
    """
    try:
        import google.generativeai as genai  # optional dependency
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(_build_prompt(scenario_summary))
        return response.text.strip()
    except Exception:
        return ""


def _build_prompt(s: dict) -> str:
    return (
        "You are a real estate analytics advisor writing a brief for a CFO.\n\n"
        f"Scenario: {s['scenario_name']} ({s['scenario_type']}, {s['horizon']} month horizon)\n"
        f"Seat Supply: {s['total_supply']:,} | Demand: {s['total_demand']:,} | Net Gap: {s['net_gap']:+,}\n"
        f"Units at Risk: {s['units_at_risk']} (RED: {s['red_count']}, AMBER: {s['amber_count']})\n"
        f"Total RTO-Based Need: {s['total_rto_need']:,} seats | "
        f"Potential Saving vs Policy: {s['potential_saving']:,} seats\n"
        f"Top Risk Unit: {s.get('top_risk_unit', 'N/A')} ({s.get('top_risk_gap', 0):+d} seats)\n"
        f"Best Opportunity: {s.get('top_opportunity', 'N/A')}\n\n"
        "Write exactly 3 short paragraphs:\n"
        "1. Current state — what the numbers show and what is at risk\n"
        "2. Biggest opportunity — what action would have the most impact and why\n"
        "3. Recommended next step — one specific, actionable sentence\n\n"
        "Rules: plain English only, no bullet points, no headers, CFO audience, max 130 words total."
    )
