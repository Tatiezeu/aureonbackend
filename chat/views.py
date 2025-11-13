# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Q
from django.utils import timezone
from reports.models import Report
from reports.serializers import ReportSerializer
import dateparser
import dateparser.search
import re
from datetime import datetime, timedelta, date

# -----------------------------------------------------------------------------
# Aureon AI Chat Assistant - Views
# - Bilingual (English / French)
# - Friendly conversational tone
# - Robust date parsing (many formats)
# - Extensive synonyms for intents & components (20+ synonyms across lists)
# - Follow-up context using Django session (last hotel, last date, last intent)
# - Differentiates hebergement / bar / cuisine revenues
# - Produces totals, expenses (sorties), and balance/profit (reste)
# - Keeps the existing structure while making code more professional & resilient
# -----------------------------------------------------------------------------

# Greetings and simple language detection tokens (expanded)
GREETINGS_EN = [
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "hiya", "howdy", "greetings"
]
GREETINGS_FR = [
    "bonjour", "salut", "bonsoir", "coucou", "bienvenue"
]

THANKS_EN = [
    "thanks", "thank you", "thx", "ty", "thanks!"
]
THANKS_FR = [
    "merci", "merci beaucoup", "merci!"
]

# Intent keywords - extended with many synonyms (english + french)
INTENT_TOTAL = [
    "total", "revenue", "revenues", "income", "sales", "turnover", "earnings",
    "receipts", "takings", "sales total", "income total", "gross", "gross revenue",
    "chiffre d'affaires", "ventes", "recette", "recettes"
]

INTENT_EXPENSES = [
    "expense", "expenses", "cost", "costs", "spend", "spending", "outflow",
    "expenditure", "expenditures", "charges", "sortie", "sorties", "depense",
    "dépense", "dépenses", "depenses", "coût", "coûts", "charges opérationnelles",
    "outlays"
]

INTENT_BALANCE = [
    "reste", "balance", "remaining", "remaining cash", "reste en caisse",
    "cash left", "leftover", "profit", "profits", "benefit", "bénéfice",
    "net", "net profit", "net income", "result", "résultat", "solde"
]

INTENT_REPORT = [
    "report", "reporting", "rapport", "summary", "overview", "details", "detail",
    "résumé", "somme", "analyse", "analyse des ventes"
]

# Component tokens (map to Report model fields) - expanded synonyms
COMPONENT_KEYWORDS = {
    "hebergement": [
        "hebergement", "hébergement", "accommodation", "accomodation", "lodging",
        "rooms", "room", "room revenue", "chambre", "chambres", "hébergements",
        "logement", "héberg", "hébergem", "room sales", "room income", "room receipts"
    ],
    "bar": [
        "bar", "bars", "bar revenue", "bar sales", "boissons", "drinks", "beverages",
        "bar takings", "bar receipts", "bar income", "bar ventes", "barre"
    ],
    "cuisine": [
        "cuisine", "kitchen", "restaurant", "resto", "food", "foods", "restaurant sales",
        "restaurant revenue", "food sales", "catering", "restauration", "cuisine ventes",
        "restaurant receipts", "cafeteria"
    ],
    # generic mapping to allow asking for overall totals by using these words
    "total_revenue": [
        "total", "revenue", "sales", "income", "takings", "receipts", "earnings",
        "gross", "turnover", "recettes", "ventes"
    ],
    # allow "expenses" synonyms to map explicitly if user mentions them without intent
    "expenses_generic": [
        "expense", "expenses", "charges", "depense", "dépense", "sortie", "sorties",
        "expenditure", "outlay", "costs", "coûts"
    ],
    "balance_generic": [
        "reste", "balance", "profit", "profits", "net", "net income", "bénéfice", "résultat"
    ]
}

# Date regex helpers
YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
DAY_RE = re.compile(r"\b([0-3]?\d)(?:st|nd|rd|th)?\b", re.IGNORECASE)

# Month names mapping (English + French variants)
MONTHS = {
    "january": 1, "janvier": 1, "jan": 1, "janv": 1,
    "february": 2, "février": 2, "fev": 2, "fevrier": 2, "feb": 2,
    "march": 3, "mars": 3, "mar": 3,
    "april": 4, "avril": 4, "apr": 4, "avr": 4,
    "may": 5, "mai": 5,
    "june": 6, "juin": 6, "jun": 6,
    "july": 7, "juillet": 7, "jul": 7,
    "august": 8, "août": 8, "aout": 8, "aug": 8,
    "september": 9, "septembre": 9, "sep": 9, "sept": 9,
    "october": 10, "octobre": 10, "oct": 10,
    "november": 11, "novembre": 11, "nov": 11,
    "december": 12, "décembre": 12, "dec": 12, "decembre": 12
}

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------

def detect_language(text: str) -> str:
    """
    Heuristic language detection (English / French) based on token presence.
    Returns 'fr' or 'en'.
    """
    if not text:
        return "en"
    txt = text.lower()
    fr_tokens = [
        "bonjour", "merci", "rapport", "mois", "année", "année", "reste", "dépense",
        "hébergement", "bar", "restaurant", "vente", "ventes", "depenses", "dépenses"
    ]
    en_tokens = [
        "hello", "thanks", "report", "month", "year", "revenue", "sales", "expense", "profit"
    ]
    fr_count = sum(1 for t in fr_tokens if t in txt)
    en_count = sum(1 for t in en_tokens if t in txt)
    # Simple bias: if French matches exceed English matches -> French
    if fr_count >= max(en_count, 1):
        return "fr"
    return "en"


def find_hotel_in_text(text: str):
    """
    Try to match hotel name from DB using case-insensitive partial match.
    Prefer exact case-insensitive match, then word-boundary, then substring.
    """
    if not text:
        return None
    lowered = text.lower()
    # Fetch distinct hotel names
    hotels = list(Report.objects.values_list("hotel_name", flat=True).distinct())
    # exact match
    for h in hotels:
        if h and h.lower() == lowered:
            return h
    # word boundary
    for h in hotels:
        if h and re.search(r"\b" + re.escape(h.lower()) + r"\b", lowered):
            return h
    # best-effort substring
    for h in hotels:
        if h and h.lower() in lowered:
            return h
    # Accept common short forms (e.g. "la dibamba" vs "hotel la dibamba")
    for h in hotels:
        if h:
            simple = re.sub(r"hotel|\bhôtel\b", "", h, flags=re.IGNORECASE).strip().lower()
            if simple and simple in lowered:
                return h
    return None


def _match_component_in_text(text: str):
    """
    Normalize component mention to canonical key defined in COMPONENT_KEYWORDS.
    Returns one of: 'hebergement', 'bar', 'cuisine', 'total_revenue', 'expenses_generic', 'balance_generic', or None.
    """
    if not text:
        return None
    txt = text.lower()
    for comp, tokens in COMPONENT_KEYWORDS.items():
        for t in tokens:
            if t in txt:
                return comp
    # extra french checks
    if any(k in txt for k in ["hébergement", "hebergement", "chambre", "logement"]):
        return "hebergement"
    if "bar" in txt and "bar " in txt or txt.endswith("bar") or "barre" in txt:
        return "bar"
    if any(k in txt for k in ["cuisine", "restaurant", "resto", "restauration", "nourriture", "food"]):
        return "cuisine"
    return None


def _robust_parse_date(text: str, prefer: str = 'first'):
    """
    Try multiple dateparser settings to robustly parse many date formats.
    prefer: 'first' or 'last' for day preference when ambiguous month-only.
    Returns a datetime or None.
    """
    if not text:
        return None
    # Try combinations of settings to account for different date orders and preferences
    settings_list = [
        {'PREFER_DAY_OF_MONTH': 'first', 'PREFER_DATES_FROM': 'past', 'STRICT_PARSING': False},
        {'PREFER_DAY_OF_MONTH': 'last', 'PREFER_DATES_FROM': 'future', 'STRICT_PARSING': False},
        {'PREFER_DAY_OF_MONTH': 'first', 'PREFER_DATES_FROM': 'current_period', 'STRICT_PARSING': False},
    ]
    for dayfirst in (False, True):
        for s in settings_list:
            s_copy = dict(s)
            s_copy['DATE_ORDER'] = 'DMY' if dayfirst else 'MDY'
            try:
                parsed = dateparser.parse(text, settings=s_copy)
            except Exception:
                parsed = None
            if parsed:
                return parsed
    # Final relaxed attempt
    try:
        return dateparser.parse(text)
    except Exception:
        return None


def _robust_search_dates(text: str):
    """
    Try several search_dates settings to extract one or more date expressions.
    Returns list of (match_text, datetime) or None.
    """
    if not text:
        return None
    combos = [
        {'PREFER_DAY_OF_MONTH': 'first', 'DATE_ORDER': 'MDY'},
        {'PREFER_DAY_OF_MONTH': 'first', 'DATE_ORDER': 'DMY'},
        {'PREFER_DAY_OF_MONTH': 'last', 'DATE_ORDER': 'DMY'},
        {'PREFER_DAY_OF_MONTH': 'first', 'DATE_ORDER': 'YMD'},
    ]
    for c in combos:
        try:
            res = dateparser.search.search_dates(text, settings=c)
        except Exception:
            res = None
        if res:
            return res
    try:
        return dateparser.search.search_dates(text)
    except Exception:
        return None


def _serialize_date_for_session(d):
    """
    Convert a date or datetime to ISO string for safe session storage.
    Accepts None.
    """
    if d is None:
        return None
    if isinstance(d, (datetime, date)):
        return d.isoformat()
    return str(d)


def _deserialize_date_from_session(s):
    """
    Convert an ISO date string back to datetime.date. Accepts None or already date.
    """
    if s is None:
        return None
    if isinstance(s, date):
        return s
    try:
        return date.fromisoformat(s)
    except Exception:
        parsed = _robust_parse_date(s)
        return parsed.date() if parsed else None


def parse_date_entities(text: str):
    """
    Parse dates from text and return a structured dict:
      - type: "single" / "month" / "year" / "range" / "none"
      - year, month, day: if available
      - start_date, end_date: normalized date objects for querying
    Accepts many formats: "October 17th 2025", "Nov 18", "18 December 2026",
    "2025-10-11", "11/12/2024", "17/10/2025", "2025.10.11", "oct 17", "17 oct", etc.
    Also infers year if omitted (prefers reasonable current/past year).
    """
    result = {"type": "none", "year": None, "month": None, "day": None, "start_date": None, "end_date": None}
    if not text:
        return result

    txt = text.lower()

    # 1) detect explicit ranges like "from X to Y", "du X au Y", "between X and Y"
    range_patterns = [
        r"(?:from|du|between)\s+(.+?)\s+(?:to|and|au|jusqu'au|jusqu au|jusqu’au|jusqu a)\s+(.+)",
        r"(.+?)\s+(?:to|and|au|jusqu'au|jusqu au|jusqu’au|jusqu a)\s+(.+)"
    ]
    for pat in range_patterns:
        m = re.search(pat, txt)
        if m:
            a, b = m.group(1).strip(), m.group(2).strip()
            parsed_a = _robust_parse_date(a, prefer='first')
            parsed_b = _robust_parse_date(b, prefer='last')
            if parsed_a and parsed_b:
                sd = parsed_a.date()
                ed = parsed_b.date()
                if sd > ed:
                    sd, ed = ed, sd
                result.update({"type": "range", "start_date": sd, "end_date": ed, "year": None, "month": None})
                return result

    # 2) use search_dates to pick up any date-like strings
    search = _robust_search_dates(txt)
    if search:
        dates = [d[1] for d in search]
        if len(dates) >= 2:
            start = dates[0].date()
            end = dates[1].date()
            if start > end:
                start, end = end, start
            result.update({"type": "range", "start_date": start, "end_date": end})
            return result

        # single detected date; inspect whether it's day-specific or month/year only
        dt = dates[0]
        result["day"] = dt.day
        result["month"] = dt.month
        result["year"] = dt.year

        # detect if text explicitly mentions a month name and/or day
        month_found = None
        for name, num in MONTHS.items():
            if name in txt:
                month_found = num
                break

        day_in_text_match = DAY_RE.search(txt)
        year_in_text_match = YEAR_RE.search(txt)

        # If month + day explicitly appear in text (with or without year), treat as single date and infer year
        if month_found and day_in_text_match:
            try:
                day_num = int(day_in_text_match.group(1))
            except Exception:
                day_num = dt.day
            if year_in_text_match:
                y = int(year_in_text_match.group(1))
            else:
                # infer sensible year
                now = timezone.now().date()
                candidate_year = dt.year if dt and getattr(dt, "year", None) else now.year
                try:
                    cand = date(candidate_year, month_found, day_num)
                    # if candidate is far in future, prefer previous year
                    if cand > now + timedelta(days=180):
                        candidate_year -= 1
                except Exception:
                    pass
                y = candidate_year
            try:
                single = date(y, month_found, day_num)
                result.update({"type": "single", "year": y, "month": month_found, "day": day_num, "start_date": single, "end_date": single})
                return result
            except Exception:
                # fallback to parsed dt
                sd = dt.date()
                result.update({"type": "single", "start_date": sd, "end_date": sd})
                return result

        # If month + year given -> month range
        if month_found and YEAR_RE.search(txt):
            y = int(YEAR_RE.search(txt).group(1))
            start_date = datetime(y, month_found, 1).date()
            if month_found == 12:
                end_date = datetime(y + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(y, month_found + 1, 1).date() - timedelta(days=1)
            result.update({"type": "month", "year": y, "month": month_found, "start_date": start_date, "end_date": end_date})
            return result

        # If only year present and no month/day -> year range
        if YEAR_RE.search(txt) and not month_found and not re.search(r"\b\d{1,2}\b", txt):
            y = int(YEAR_RE.search(txt).group(1))
            result.update({"type": "year", "year": y, "start_date": datetime(y, 1, 1).date(), "end_date": datetime(y, 12, 31).date()})
            return result

        # Otherwise treat parsed dt as single day
        sd = dt.date()
        result.update({"type": "single", "start_date": sd, "end_date": sd, "year": sd.year, "month": sd.month, "day": sd.day})
        return result

    # 3) manual month/day/year detection if nothing parsed by dateparser
    for name, num in MONTHS.items():
        if name in txt:
            y_match = YEAR_RE.search(txt)
            day_match = DAY_RE.search(txt)
            now = timezone.now().date()
            if day_match:
                day_num = int(day_match.group(1))
                if y_match:
                    y = int(y_match.group(1))
                else:
                    # infer year
                    parsed_year = now.year
                    try:
                        cand = date(parsed_year, num, day_num)
                        if cand > now + timedelta(days=180):
                            parsed_year -= 1
                    except Exception:
                        pass
                    y = parsed_year
                try:
                    single = date(y, num, day_num)
                    result.update({"type": "single", "year": y, "month": num, "day": day_num, "start_date": single, "end_date": single})
                    return result
                except Exception:
                    pass
            # month only
            y = int(y_match.group(1)) if y_match else now.year
            start_date = datetime(y, num, 1).date()
            if num == 12:
                end_date = datetime(y + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(y, num + 1, 1).date() - timedelta(days=1)
            result.update({"type": "month", "year": y, "month": num, "start_date": start_date, "end_date": end_date})
            return result

    # 4) detect standalone year only
    y_match = YEAR_RE.search(txt)
    if y_match:
        y = int(y_match.group(1))
        result.update({"type": "year", "year": y, "start_date": datetime(y, 1, 1).date(), "end_date": datetime(y, 12, 31).date()})
        return result

    return result


# -----------------------------------------------------------------------------
# Chat API View
# -----------------------------------------------------------------------------

class ChatBotAPIView(APIView):
    """
    Main chat endpoint for Aureon AI assistant.
    Handles POST with payload: {"message": "<user message>"}
    Responds in JSON: {"reply": "<bot reply>"}.
    """

    def post(self, request):
        # Validate input
        raw_message = request.data.get("message", "")
        if not isinstance(raw_message, str) or not raw_message.strip():
            return Response({"reply": "Please send a non-empty message."}, status=status.HTTP_400_BAD_REQUEST)

        user_message = raw_message.strip()
        lowered = user_message.lower()

        # Detect language and friendly greeting style
        lang = detect_language(lowered)

        # Friendly, ChatGPT-like opening after greeting: templates will include friendly tone
        # Response templates (English / French) - friendly style
        if lang == "fr":
            templates = {
                "greeting": "Bonjour ! Je suis Aureon AI, votre assistant. Comment puis-je vous aider aujourd'hui ? (ex: 'Total des ventes Hotel La Dibamba novembre 2025')",
                "ask_more": "Pouvez-vous préciser l'hôtel, la période (jour/mois/année) ou le type (hébergement, bar, restaurant) ?",
                "no_reports": "Désolé, il n'y a pas de rapports pour {hotel} pour la période demandée.",
                "total_reply": "Voici le total {component_text} pour {hotel} du {start} au {end} : XAF {amount:,.2f}.",
                "expenses_reply": "Voici le total des dépenses (sorties) {component_text} pour {hotel} du {start} au {end} : XAF {amount:,.2f}.",
                "balance_reply": "Le reste / profit {component_text} pour {hotel} du {start} au {end} est : XAF {amount:,.2f}.",
                "expenses_list_reply": "Voici la liste des dépenses pour {hotel} le {date} : {items}. Total dépenses: XAF {amount:,.2f}.",
                "fallback": "Désolé, je n'ai pas compris. Je peux fournir des rapports (ventes, dépenses, reste). Par ex. 'Total revenus Hotel La Dibamba Novembre 2025'."
            }
        else:
            templates = {
                "greeting": "Hello! I'm Aureon AI, your assistant. How can I help today? (e.g. 'Total sales Hotel La Dibamba November 2025')",
                "ask_more": "Please specify the hotel, period (day/month/year) or component (hebergement, bar, restaurant).",
                "no_reports": "Sorry, there are no reports for {hotel} for the requested period.",
                "total_reply": "Here is the total {component_text} for {hotel} from {start} to {end}: XAF {amount:,.2f}.",
                "expenses_reply": "Here is the total expenses (sorties) {component_text} for {hotel} from {start} to {end}: XAF {amount:,.2f}.",
                "balance_reply": "The remaining cash / profit {component_text} for {hotel} from {start} to {end} is: XAF {amount:,.2f}.",
                "expenses_list_reply": "Here is the list of expenses for {hotel} on {date}: {items}. Total expenses: XAF {amount:,.2f}.",
                "fallback": "Sorry, I didn't quite get that. I can provide reports (sales, expenses, remaining). Example: 'Total revenue Hotel La Dibamba November 2025'."
            }

        # 1) Handle greetings early to be chatty & friendly
        if any(g in lowered for g in GREETINGS_EN + GREETINGS_FR):
            return Response({"reply": templates["greeting"]})

        # 2) Handle thanks & polite closings
        if any(t in lowered for t in THANKS_EN + THANKS_FR):
            if lang == "fr":
                return Response({"reply": "Avec plaisir ! Si vous avez d'autres questions sur les rapports, je suis là."})
            return Response({"reply": "You're welcome! If you need more report info, just ask."})

        # 3) Extract hotel name (if present)
        hotel = find_hotel_in_text(lowered)

        # 4) Parse date entities robustly
        date_info = parse_date_entities(lowered)

        # 5) Detect component and intent
        component_mentioned = _match_component_in_text(lowered)
        # wide intent detection using synonyms
        intent = None
        for k in INTENT_EXPENSES:
            if k in lowered:
                intent = "expenses"
                break
        if not intent:
            for k in INTENT_BALANCE:
                if k in lowered:
                    intent = "balance"
                    break
        if not intent:
            for k in INTENT_TOTAL:
                if k in lowered:
                    intent = "total"
                    break
        # fallback: if the user asked generically about a report -> total
        if not intent:
            if any(k in lowered for k in INTENT_REPORT) or lowered.strip().endswith('?') or len(lowered.split()) <= 6:
                intent = "total"

        # 6) Session-based follow ups: last hotel, date, intent
        sess = request.session
        last_hotel = sess.get("last_hotel")
        last_date_serialized = sess.get("last_date")  # stored as (type, start_iso, end_iso)
        last_intent = sess.get("last_intent")

        # Deserialize last_date if present
        last_date = None
        if last_date_serialized and isinstance(last_date_serialized, (list, tuple)) and len(last_date_serialized) == 3:
            try:
                ld_type = last_date_serialized[0]
                ld_start = _deserialize_date_from_session(last_date_serialized[1])
                ld_end = _deserialize_date_from_session(last_date_serialized[2])
                last_date = (ld_type, ld_start, ld_end)
            except Exception:
                last_date = None

        # Use session hotel if user did not specify but message appears short or contains follow-up pronouns
        if not hotel and last_hotel:
            if len(lowered.split()) < 10 or any(word in lowered for word in ["it", "that", "this", "le", "la", "l'", "same", "also", "and", "aussi"]):
                hotel = last_hotel

        # Update session hotel if user provided one now
        if hotel:
            sess["last_hotel"] = hotel

        # Update date session if user provided date
        if date_info and date_info.get("type") and date_info.get("type") != "none":
            sd_iso = _serialize_date_for_session(date_info.get("start_date"))
            ed_iso = _serialize_date_for_session(date_info.get("end_date"))
            sess["last_date"] = (date_info.get("type"), sd_iso, ed_iso)
        else:
            # interpret "this month"/"ce mois-ci", "this year"/"cette année" into session
            if ("this month" in lowered) or ("ce mois" in lowered) or ("ce mois-ci" in lowered):
                now = timezone.now().date()
                start = datetime(now.year, now.month, 1).date()
                if now.month == 12:
                    end = datetime(now.year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    end = datetime(now.year, now.month + 1, 1).date() - timedelta(days=1)
                sess["last_date"] = ("month", _serialize_date_for_session(start), _serialize_date_for_session(end))
                date_info = {"type": "month", "start_date": start, "end_date": end}
            elif ("this year" in lowered) or ("cette année" in lowered) or ("cette annee" in lowered):
                now = timezone.now().date()
                start = datetime(now.year, 1, 1).date()
                end = datetime(now.year, 12, 31).date()
                sess["last_date"] = ("year", _serialize_date_for_session(start), _serialize_date_for_session(end))
                date_info = {"type": "year", "start_date": start, "end_date": end}
            elif not date_info or date_info.get("type") == "none":
                # fallback to session date if exists
                if last_date:
                    date_info = {"type": last_date[0], "start_date": last_date[1], "end_date": last_date[2]}

        # Determine intent via session if undetermined and there's a last_intent (useful for follow-ups like "what about bar?")
        if not intent and component_mentioned and last_intent:
            intent = last_intent

        # Default fallback if still no intent
        if not intent:
            return Response({"reply": templates["fallback"]})

        # Save last_intent for follow-ups
        sess["last_intent"] = intent
        request.session.modified = True

        # If both hotel and date missing even after session fallback, ask for clarification
        if not hotel and (not date_info or date_info.get("type") == "none"):
            return Response({"reply": templates["ask_more"]})

        # Build queryset filters: hotel & date filters
        reports_qs = Report.objects.all()
        if hotel:
            # prefer exact match (case insensitive) but allow contains as fallback
            reports_qs = reports_qs.filter(hotel_name__iexact=hotel)

        # Apply date filter
        if date_info and date_info.get("type") == "single" and date_info.get("start_date"):
            sd = date_info["start_date"]
            reports_qs = reports_qs.filter(created_at__date=sd)
        elif date_info and date_info.get("start_date") and date_info.get("end_date"):
            sd = date_info["start_date"]
            ed = date_info["end_date"]
            reports_qs = reports_qs.filter(created_at__date__gte=sd, created_at__date__lte=ed)

        # If still no reports, return a no-report message
        if not reports_qs.exists():
            start_str = date_info.get("start_date").strftime("%Y-%m-%d") if date_info and date_info.get("start_date") else "the specified period"
            end_str = date_info.get("end_date").strftime("%Y-%m-%d") if date_info and date_info.get("end_date") else ""
            # compose period display
            if start_str and end_str and start_str != end_str:
                period_display = f"{start_str} to {end_str}"
            else:
                period_display = start_str
            return Response({"reply": templates["no_reports"].format(hotel=hotel or "the hotel")})

        # Check whether user specifically asked for an expenses list or detailed report
        wants_expense_list = False
        lowered_trigger_phrases = [
            "list expenses", "list of expenses", "expenses list", "detailed expenses",
            "liste des dépenses", "liste des depenses", "détail des dépenses", "rapport dépenses",
            "rapport depenses", "resume des dépenses", "résumé des dépenses", "détaillé dépenses", "détail dépenses"
        ]
        for p in lowered_trigger_phrases:
            if p in lowered:
                wants_expense_list = True
                break
        # also detect french combined expressions that often request expense lists
        if any(x in lowered for x in ["liste", "détail", "détaille", "détaillé"]) and any(y in lowered for y in ["dépense", "depense", "sortie"]):
            wants_expense_list = True

        # If user wants expense listing and intent is expenses, produce detailed listing
        if wants_expense_list and intent == "expenses":
            # Collect report entries within filtered queryset
            report_entries = reports_qs.order_by('created_at').values(
                'created_at', 'total_expenses', 'montant_hebergement', 'montant_bar', 'montant_cuisine', 'reste_en_caisse'
            )

            if not report_entries:
                return Response({"reply": templates["no_reports"].format(hotel=hotel or "the hotel")})

            items = []
            totals = {"expenses": 0, "heberg": 0, "bar": 0, "cuisine": 0, "reste": 0}
            for r in report_entries:
                created_at = r.get('created_at')
                date_str = created_at.strftime("%Y-%m-%d") if isinstance(created_at, datetime) else str(created_at)
                exp_val = r.get('total_expenses') or 0
                he_val = r.get('montant_hebergement') or 0
                ba_val = r.get('montant_bar') or 0
                cu_val = r.get('montant_cuisine') or 0
                re_val = r.get('reste_en_caisse') or 0

                totals["expenses"] += exp_val
                totals["heberg"] += he_val
                totals["bar"] += ba_val
                totals["cuisine"] += cu_val
                totals["reste"] += re_val

                items.append(f"{date_str}: expenses XAF {exp_val:,.2f}, hebergement XAF {he_val:,.2f}, bar XAF {ba_val:,.2f}, restaurant XAF {cu_val:,.2f}, reste XAF {re_val:,.2f}")

            items_joined = " ; ".join(items)
            summary = f"Total expenses: XAF {totals['expenses']:,.2f}, hebergement: XAF {totals['heberg']:,.2f}, bar: XAF {totals['bar']:,.2f}, restaurant: XAF {totals['cuisine']:,.2f}, reste: XAF {totals['reste']:,.2f}"

            # Prepare localized date display for template
            date_display = date_info.get("start_date").strftime("%Y-%m-%d") if date_info and date_info.get("start_date") else "the specified period"

            return Response({"reply": templates["expenses_list_reply"].format(
                hotel=hotel or "the hotel",
                date=date_display,
                items=items_joined + ". " + summary,
                amount=totals['expenses']
            )})

        # Aggregate sums across matching reports
        agg = reports_qs.aggregate(
            hebergement_sum=Sum('montant_hebergement'),
            bar_sum=Sum('montant_bar'),
            cuisine_sum=Sum('montant_cuisine'),
            expenses_sum=Sum('total_expenses'),
            reste_sum=Sum('reste_en_caisse')
        )

        heberg = agg.get('hebergement_sum') or 0
        bar_sum = agg.get('bar_sum') or 0
        cuisine = agg.get('cuisine_sum') or 0
        total_revenue = (heberg or 0) + (bar_sum or 0) + (cuisine or 0)
        total_expenses = agg.get('expenses_sum') or 0
        total_reste = agg.get('reste_sum') or (total_revenue - total_expenses)

        # Decide which component to show (if any)
        comp = component_mentioned  # canonical key or None

        component_text = ""
        amount = None

        # When user asks for component-specific metrics, attempt to give component-level revenue if available.
        if comp == "hebergement":
            component_text = "hébergement" if lang == "fr" else "hebergement"
            if intent == "total":
                amount = float(heberg or 0)
            elif intent == "expenses":
                # per-component expenses are not stored; fallback to overall expenses
                amount = float(total_expenses)
            elif intent == "balance":
                # approximate component profit: component revenue - total expenses (coarse)
                amount = float((heberg or 0) - (total_expenses or 0))
        elif comp == "bar":
            component_text = "bar"
            if intent == "total":
                amount = float(bar_sum or 0)
            elif intent == "expenses":
                amount = float(total_expenses)
            elif intent == "balance":
                amount = float((bar_sum or 0) - (total_expenses or 0))
        elif comp == "cuisine":
            component_text = "restaurant" if lang == "fr" else "restaurant"
            if intent == "total":
                amount = float(cuisine or 0)
            elif intent == "expenses":
                amount = float(total_expenses)
            elif intent == "balance":
                amount = float((cuisine or 0) - (total_expenses or 0))
        else:
            # No specific component: provide overall totals
            component_text = "total" if lang == "en" else "total"
            if intent == "total":
                amount = float(total_revenue)
            elif intent == "expenses":
                amount = float(total_expenses)
            elif intent == "balance":
                amount = float(total_reste)

        # Format period display
        start = date_info.get("start_date")
        end = date_info.get("end_date")
        if start and end:
            if start == end:
                period_display = start.strftime("%Y-%m-%d")
            else:
                period_display = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        else:
            period_display = "the specified period" if lang == "en" else "la période spécifiée"

        # Compose reply localized & friendly
        if intent == "total":
            # Friendly wording
            if lang == "fr":
                # if component specified include it, else generic friendly phrase
                comp_text_for_template = f"{component_text}" if component_text else ""
                return Response({
                    "reply": templates["total_reply"].format(
                        component_text=comp_text_for_template,
                        hotel=hotel or "l'hôtel",
                        start=start.strftime("%Y-%m-%d") if start else period_display,
                        end=end.strftime("%Y-%m-%d") if end else "",
                        amount=amount
                    )
                })
            else:
                comp_text_for_template = f"{component_text}" if component_text else ""
                return Response({
                    "reply": templates["total_reply"].format(
                        component_text=comp_text_for_template,
                        hotel=hotel or "the hotel",
                        start=start.strftime("%Y-%m-%d") if start else period_display,
                        end=end.strftime("%Y-%m-%d") if end else "",
                        amount=amount
                    )
                })

        if intent == "expenses":
            if lang == "fr":
                return Response({
                    "reply": templates["expenses_reply"].format(
                        component_text=component_text,
                        hotel=hotel or "l'hôtel",
                        start=start.strftime("%Y-%m-%d") if start else period_display,
                        end=end.strftime("%Y-%m-%d") if end else "",
                        amount=amount
                    )
                })
            else:
                return Response({
                    "reply": templates["expenses_reply"].format(
                        component_text=component_text,
                        hotel=hotel or "the hotel",
                        start=start.strftime("%Y-%m-%d") if start else period_display,
                        end=end.strftime("%Y-%m-%d") if end else "",
                        amount=amount
                    )
                })

        if intent == "balance":
            if lang == "fr":
                return Response({
                    "reply": templates["balance_reply"].format(
                        component_text=component_text,
                        hotel=hotel or "l'hôtel",
                        start=start.strftime("%Y-%m-%d") if start else period_display,
                        end=end.strftime("%Y-%m-%d") if end else "",
                        amount=amount
                    )
                })
            else:
                return Response({
                    "reply": templates["balance_reply"].format(
                        component_text=component_text,
                        hotel=hotel or "the hotel",
                        start=start.strftime("%Y-%m-%d") if start else period_display,
                        end=end.strftime("%Y-%m-%d") if end else "",
                        amount=amount
                    )
                })

        # Final fallback
        return Response({"reply": templates["fallback"]})