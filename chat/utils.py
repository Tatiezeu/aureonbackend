import os
import logging
from django.conf import settings
from reports.models import Report
from decimal import Decimal

logger = logging.getLogger(__name__)

# --- Helpers to create textual context about a Report ---
def build_report_summary(report: Report) -> str:
    """
    Returns a short plain-text summary of the report suitable to send to the LLM.
    Keep it concise so prompts stay small.
    """
    if not report:
        return ""

    def fmt_amount(x: Decimal):
        try:
            return f"{int(x):,}"
        except Exception:
            return str(x)

    parts = [
        f"Hotel: {report.hotel_name}",
        f"Date: {report.created_at.strftime('%Y-%m-%d')}",
        f"Hébergement: {fmt_amount(report.montant_hebergement)}",
        f"Bar: {fmt_amount(report.montant_bar)}",
        f"Cuisine: {fmt_amount(report.montant_cuisine)}",
        f"Total amount: {fmt_amount(report.total_amount)}",
        f"Total expenses: {fmt_amount(report.total_expenses)}",
        f"Reste en caisse: {fmt_amount(report.reste_en_caisse)}",
    ]
    # add first few expenses (if any)
    expenses = report.expenses.all().order_by('created_at')[:8]
    if expenses.exists():
        parts.append("Expenses (latest up to 8):")
        for e in expenses:
            parts.append(f" - {e.label}: {fmt_amount(e.amount)}")

    return "\n".join(parts)


# --- Gemini caller: attempt SDK, fallback to direct HTTP ---
def query_gemini_flash(prompt: str, max_tokens: int = 512) -> str:
    """
    Query Gemini Flash and return text answer.
    - Tries to use google.generativeai SDK if installed.
    - Falls back to a simple HTTP POST using requests if SDK not available.
    Update the model name if your account uses a different model id.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in settings or environment.")

    # Prefer SDK if available
    try:
        import google.generativeai as genai
        # NOTE: package name and usage may change with versions; this is a commonly used pattern.
        genai.configure(api_key=api_key)
        # model id below is a commonly used flash model name; change if needed
        model = "gemini-1.5-flash"  # adjust if your key requires another model like "gemini-flash" etc.
        resp = genai.generate_text(model=model, prompt=prompt, max_output_tokens=max_tokens)
        # parse response — SDK returns different shapes depending on version
        if hasattr(resp, "text"):
            return resp.text
        # fallback: dict-style
        if isinstance(resp, dict) and "candidates" in resp and len(resp["candidates"]) > 0:
            return resp["candidates"][0].get("content", "")
        return str(resp)
    except Exception as e:
        logger.info("SDK call failed or not available, falling back to HTTP request: %s", e)

    # --- HTTP fallback ---
    try:
        import requests
        url = "https://generative.googleapis.com/v1beta2/models/gemini-1.5-flash:generateText"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # body structure may vary per API version; adjust if your Google API expects a different schema
        body = {
            "prompt": {
                "text": prompt
            },
            "maxOutputTokens": max_tokens
        }
        r = requests.post(url, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        # parsing — this depends on API shape
        if isinstance(data, dict):
            # try common places
            if "candidates" in data and len(data["candidates"]) > 0:
                return data["candidates"][0].get("content", "")
            if "output" in data and isinstance(data["output"], list):
                return " ".join([item.get("content", "") for item in data["output"] if isinstance(item, dict)])
            # last resort
            return str(data)
        return str(data)
    except Exception as e:
        logger.exception("Gemini HTTP fallback failed: %s", e)
        raise RuntimeError("Failed to contact Gemini API. See server logs for details.") from e


def build_prompt(user_question: str, report: Report = None) -> str:
    """
    Construct a clean prompt for the LLM with explicit instructions and context.
    Keep the instructions short and explicit for consistent answers.
    """
    system = (
        "You are Aureon Assistant, a helpful assistant that answers questions about hotel financial reports. "
        "Be brief, give numbers with units (XAF) where possible, and if you are not sure, say you are not sure and explain how to find the data (e.g., API endpoint)."
    )

    report_section = ""
    if report:
        report_section = "\n\nReport summary:\n" + build_report_summary(report)

    prompt = f"{system}\n\nUser question: {user_question}{report_section}\n\nAnswer concisely in plain text."
    return prompt
