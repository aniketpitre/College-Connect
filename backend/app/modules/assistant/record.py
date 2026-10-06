"""
"Ask my record" (plan 5.4, 5.5; unique feature U1): short, structured excerpts of the asker's own
fees, certificates, attendance and marks, passed to the help desk next to the document excerpts
and cited like them ("Your fee account, as of 06-10-2026").

- Only the caller's own record (a parent: the child picked with X-Child, and only the areas the
  student shares with parents). Built through the same service functions as the student's own
  pages, so the same scoping applies; nothing here takes a student id from the request.
- Only the areas the question is about (keywords in English, Hindi and Marathi).
- Written in the asker's language by templates, so the excerpt is exact even without an AI key:
  then a personal question ("my fees", "मला किती फी") is answered with the excerpt itself.
- Never logged: the help-desk log keeps the question, language and the source's name only.
"""

import re
from collections.abc import Callable
from typing import Any

from app.core import clock
from app.core.auth import AuthContext
from app.core.errors import AppError
from app.core.money import format_inr

AREAS = ("fees", "certificates", "attendance", "results")

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fees": (
        "fee", "fees", "dues", "pay", "paid", "payment", "balance", "owe", "installment", "instalment",
        "receipt", "outstanding", "शुल्क", "फी", "फीस", "बाकी", "थकबाकी", "हप्ता", "किस्त", "पावती", "रसीद", "भरायची",
        "भरनी", "भरना",
    ),
    "certificates": (
        "certificate", "certificates", "bonafide", "tc", "transfer", "migration", "noc", "character",
        "प्रमाणपत्र", "दाखला", "बोनाफाइड", "बोनाफाईड",
    ),
    "attendance": (
        "attendance", "present", "absent", "bunk", "lectures", "lecture", "उपस्थिति", "हाजिरी", "हजेरी",
        "उपस्थिती", "गैरहजर", "अनुपस्थित",
    ),
    "results": (
        "marks", "mark", "result", "results", "sgpa", "cgpa", "grade", "grades", "backlog", "backlogs", "kt",
        "internal", "internals", "score", "अंक", "गुण", "निकाल", "परिणाम", "नतीजा", "बॅकलॉग",
    ),
}  # fmt: skip
# "my fees", "मला किती फी": the question is about the asker's own record.
_PERSONAL = (
    "my", "me", "i", "mine", "i'm", "am", "मेरा", "मेरी", "मेरे", "मुझे", "मैं", "मला", "माझा", "माझी",
    "माझे", "माझ्या", "मी", "हमारा", "आमचा",
)  # fmt: skip


def _words(question: str) -> set[str]:
    return set(re.findall(r"[\wऀ-ॿ']+", question.lower()))


def areas_asked(question: str) -> list[str]:
    words = _words(question)
    text = question.lower()

    def hit(k: str) -> bool:
        # Devanagari words also match inside longer forms (शुल्काची, फीस); English ones whole.
        return k in text if re.search(r"[ऀ-ॿ]", k) else k in words

    return [a for a in AREAS if any(hit(k) for k in _KEYWORDS[a])]


def is_personal(question: str) -> bool:
    return bool(_words(question) & set(_PERSONAL))


# --- the excerpts, in the asker's language ----------------------------------------------------

T: dict[str, dict[str, Any]] = {
    "en": {
        "fees_title": "Your fee account",
        "attendance_title": "Your attendance",
        "results_title": "Your marks and results",
        "certificates_title": "Your certificate requests",
        "document": lambda d: f"Your record, as of {d}",
        "fees": lambda y, demand, charges, paid, relief, balance: (
            f"Fee account for {y}: fees demanded {demand}; other charges {charges}; paid {paid}; "
            f"concessions and scholarships {relief}. Balance still to pay: {balance}."
        ),
        "no_fees": "No fees have been demanded yet for this year.",
        "overdue": lambda a: f"Of this, {a} is overdue.",
        "installment": lambda label, d, due, late: (
            f"{label} (due {d}): {due} still to pay{' (overdue)' if late else ''}."
        ),
        "installment_paid": lambda label, d: f"{label} (due {d}): paid.",
        "last_receipt": lambda n, d, a: f"Last receipt {n} on {d} for {a}.",
        "attendance": lambda pct, att, held, minimum: (
            f"Overall attendance {pct}% ({att} of {held} lectures); the minimum required is {minimum}%."
        ),
        "no_attendance": "No lectures have been recorded yet.",
        "subject_att": lambda code, name, pct, att, held: f"{code} {name}: {pct}% ({att} of {held})",
        "must_attend": lambda n: f"must attend the next {n} lectures to reach the minimum",
        "can_miss": lambda n: f"can miss {n} more",
        "internal": lambda code, name, total, out_of: f"Internal marks {code} {name}: {total} out of {out_of}.",
        "cgpa": lambda c, cr: f"CGPA {c} ({cr} credits earned).",
        "result": lambda exam, sgpa, outcome: f"Latest result, {exam}: SGPA {sgpa}, {outcome}.",
        "backlogs": lambda subjects: f"Subjects still to clear: {subjects}.",
        "no_backlogs": "No subjects to clear.",
        "no_results": "No marks or results have been published yet.",
        "request": lambda name, d, status, promised, late: (
            f"{name}, requested on {d}: {status}"
            + (f"; promised by {promised}{' (overdue)' if late else ''}" if promised else "")
            + "."
        ),
        "no_requests": "No certificate requests.",
        "dues": lambda items: f"Dues to clear before a TC or migration certificate: {items}.",
        "status": {"requested": "requested", "verified": "verified by the office", "signed": "signed",
                   "ready": "ready to collect", "rejected": "rejected"},
        "outcome": {"pass": "passed", "atkt": "allowed to keep terms (ATKT)", "absent": "absent"},
    },
    "hi": {
        "fees_title": "आपका शुल्क खाता",
        "attendance_title": "आपकी उपस्थिति",
        "results_title": "आपके अंक और परिणाम",
        "certificates_title": "आपके प्रमाणपत्र आवेदन",
        "document": lambda d: f"आपका रिकॉर्ड, {d} तक",
        "fees": lambda y, demand, charges, paid, relief, balance: (
            f"{y} का शुल्क खाता: माँगा गया शुल्क {demand}; अन्य शुल्क {charges}; भुगतान {paid}; "
            f"छूट और छात्रवृत्ति {relief}। अभी भरना बाकी: {balance}।"
        ),
        "no_fees": "इस वर्ष का शुल्क अभी तय नहीं हुआ है।",
        "overdue": lambda a: f"इसमें से {a} की तारीख निकल चुकी है।",
        "installment": lambda label, d, due, late: (
            f"{label} ({d} तक): {due} बाकी{' (तारीख निकल चुकी)' if late else ''}।"
        ),
        "installment_paid": lambda label, d: f"{label} ({d} तक): भरी गई।",
        "last_receipt": lambda n, d, a: f"अंतिम रसीद {n}, {d} को, {a}।",
        "attendance": lambda pct, att, held, minimum: (
            f"कुल उपस्थिति {pct}% ({held} में से {att} व्याख्यान); न्यूनतम आवश्यक {minimum}%।"
        ),
        "no_attendance": "अभी तक कोई व्याख्यान दर्ज नहीं हुआ है।",
        "subject_att": lambda code, name, pct, att, held: f"{code} {name}: {pct}% ({held} में से {att})",
        "must_attend": lambda n: f"न्यूनतम तक पहुँचने के लिए अगले {n} व्याख्यान ज़रूरी",
        "can_miss": lambda n: f"{n} और छोड़ सकते हैं",
        "internal": lambda code, name, total, out_of: f"आंतरिक अंक {code} {name}: {out_of} में से {total}।",
        "cgpa": lambda c, cr: f"CGPA {c} ({cr} क्रेडिट अर्जित)।",
        "result": lambda exam, sgpa, outcome: f"नवीनतम परिणाम, {exam}: SGPA {sgpa}, {outcome}।",
        "backlogs": lambda subjects: f"बाकी विषय: {subjects}।",
        "no_backlogs": "कोई विषय बाकी नहीं।",
        "no_results": "अभी तक कोई अंक या परिणाम प्रकाशित नहीं हुआ है।",
        "request": lambda name, d, status, promised, late: (
            f"{name}, {d} को आवेदन: {status}"
            + (f"; {promised} तक देने का वादा{' (तारीख निकल चुकी)' if late else ''}" if promised else "")
            + "।"
        ),
        "no_requests": "कोई प्रमाणपत्र आवेदन नहीं।",
        "dues": lambda items: f"TC या माइग्रेशन प्रमाणपत्र से पहले चुकाना बाकी: {items}।",
        "status": {"requested": "आवेदन किया", "verified": "कार्यालय द्वारा जाँचा गया", "signed": "हस्ताक्षरित",
                   "ready": "लेने के लिए तैयार", "rejected": "अस्वीकृत"},
        "outcome": {"pass": "उत्तीर्ण", "atkt": "ATKT", "absent": "अनुपस्थित"},
    },
    "mr": {
        "fees_title": "तुमचे शुल्क खाते",
        "attendance_title": "तुमची उपस्थिती",
        "results_title": "तुमचे गुण आणि निकाल",
        "certificates_title": "तुमचे प्रमाणपत्र अर्ज",
        "document": lambda d: f"तुमची नोंद, {d} पर्यंत",
        "fees": lambda y, demand, charges, paid, relief, balance: (
            f"{y} चे शुल्क खाते: मागणी केलेले शुल्क {demand}; इतर शुल्क {charges}; भरलेले {paid}; "
            f"सवलत आणि शिष्यवृत्ती {relief}. अजून भरायची शिल्लक: {balance}."
        ),
        "no_fees": "या वर्षाचे शुल्क अजून ठरलेले नाही.",
        "overdue": lambda a: f"यापैकी {a} ची मुदत संपली आहे.",
        "installment": lambda label, d, due, late: f"{label} ({d} पर्यंत): {due} भरायचे{' (मुदत संपली)' if late else ''}.",
        "installment_paid": lambda label, d: f"{label} ({d} पर्यंत): भरले.",
        "last_receipt": lambda n, d, a: f"शेवटची पावती {n}, {d} रोजी, {a}.",
        "attendance": lambda pct, att, held, minimum: (
            f"एकूण उपस्थिती {pct}% ({held} पैकी {att} तासिका); किमान आवश्यक {minimum}%."
        ),
        "no_attendance": "अजून कोणतीही तासिका नोंदलेली नाही.",
        "subject_att": lambda code, name, pct, att, held: f"{code} {name}: {pct}% ({held} पैकी {att})",
        "must_attend": lambda n: f"किमान गाठण्यासाठी पुढच्या {n} तासिका आवश्यक",
        "can_miss": lambda n: f"आणखी {n} चुकवू शकता",
        "internal": lambda code, name, total, out_of: f"अंतर्गत गुण {code} {name}: {out_of} पैकी {total}.",
        "cgpa": lambda c, cr: f"CGPA {c} ({cr} क्रेडिट मिळवले).",
        "result": lambda exam, sgpa, outcome: f"नवीनतम निकाल, {exam}: SGPA {sgpa}, {outcome}.",
        "backlogs": lambda subjects: f"राहिलेले विषय: {subjects}.",
        "no_backlogs": "कोणताही विषय राहिलेला नाही.",
        "no_results": "अजून कोणतेही गुण किंवा निकाल जाहीर झालेले नाहीत.",
        "request": lambda name, d, status, promised, late: (
            f"{name}, {d} रोजी अर्ज: {status}"
            + (f"; {promised} पर्यंत देण्याचे आश्वासन{' (मुदत संपली)' if late else ''}" if promised else "")
            + "."
        ),
        "no_requests": "कोणतेही प्रमाणपत्र अर्ज नाहीत.",
        "dues": lambda items: f"TC किंवा मायग्रेशन प्रमाणपत्रापूर्वी भरायची थकबाकी: {items}.",
        "status": {"requested": "अर्ज केला", "verified": "कार्यालयाने तपासला", "signed": "स्वाक्षरी झाली",
                   "ready": "घेण्यास तयार", "rejected": "नाकारला"},
        "outcome": {"pass": "उत्तीर्ण", "atkt": "ATKT", "absent": "गैरहजर"},
    },
}  # fmt: skip

LINKS = {
    "fees": "/app/my-fees",
    "attendance": "/app/attendance",
    "results": "/app/exams",
    "certificates": "/app/certificates",
}
# The documents that explain each area, for citing next to the record (keyword fallback).
DOC_CATEGORIES = {
    "fees": {"fees", "notices"},
    "results": {"examinations", "notices"},
    "attendance": {"examinations", "notices"},
    "certificates": {"admissions", "notices"},
}


# English words that find the document explaining each area (the documents are in English).
HINTS = {
    "fees": "fee payment deadline installment late fine",
    "results": "result revaluation backlog examination",
    "attendance": "attendance minimum percentage eligibility",
    "certificates": "certificate bonafide documents office",
}


def _d(iso: str | None) -> str:
    """'2026-07-16' → '16-07-2026' (the same in every language)."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{d}-{m}-{y}"


def _fees(ctx: AuthContext, t: dict[str, Any]) -> str:
    from app.modules.portal import service as portal

    f = portal.my_fees(ctx, None)
    if not f.get("has_demand") and not f.get("balance"):
        return t["no_fees"]
    year = next((y["name"] for y in f.get("years", []) if y["id"] == f.get("academic_year_id")), "")
    relief = f.get("concessions", 0) + f.get("scholarships", 0)
    lines = [
        t["fees"](
            year, format_inr(f["demand"]), format_inr(f["charges"]), format_inr(f["paid"]),
            format_inr(relief), format_inr(f["balance"]),
        )
    ]  # fmt: skip
    if f.get("overdue"):
        lines.append(t["overdue"](format_inr(f["overdue"])))
    for i in f.get("installments", []):
        if i["due"] > 0:
            lines.append(t["installment"](i["label"], _d(i["due_date"]), format_inr(i["due"]), i["overdue"]))
        else:
            lines.append(t["installment_paid"](i["label"], _d(i["due_date"])))
    issued = [r for r in f.get("receipts") or [] if r.get("status") != "cancelled"]
    if issued:
        r = issued[0]
        lines.append(t["last_receipt"](r["number"], _d(r["collected_at"]), format_inr(r["amount"])))
    return " ".join(lines)


def _attendance(ctx: AuthContext, t: dict[str, Any]) -> str:
    from app.modules.attendance import stats

    a = stats.my_attendance(ctx)
    o = a.get("overall") or {}
    if not o.get("held"):
        return t["no_attendance"]
    lines = [t["attendance"](o["percent"], o["attended"], o["held"], a["minimum"])]
    parts = []
    for s in a.get("subjects", []):
        part = t["subject_att"](s["code"], s["name"], s["percent"], s["attended"], s["held"])
        if s.get("must_attend"):
            part += f" ({t['must_attend'](s['must_attend'])})"
        elif s.get("can_miss") is not None:
            part += f" ({t['can_miss'](s['can_miss'])})"
        parts.append(part)
    return " ".join(lines) + " " + "; ".join(parts) + "."


def _results(ctx: AuthContext, t: dict[str, Any]) -> str:
    from app.modules.marks import service as marks
    from app.modules.results import service as results

    lines = [t["internal"](m["code"], m["name"], m["total"], m["out_of"]) for m in marks.my_marks(ctx)]
    r = results.my_results(ctx)
    if r.get("results"):
        latest = r["results"][0]
        outcome = t["outcome"].get(latest["outcome"], latest["outcome"])
        lines.append(t["result"](latest["exam"], latest["sgpa"], outcome))
        if r.get("cgpa") is not None:
            lines.append(t["cgpa"](r["cgpa"], r["credits_earned"]))
        backlogs = ", ".join(f"{b['code']} {b['name']}" for b in r.get("backlogs", []))
        lines.append(t["backlogs"](backlogs) if backlogs else t["no_backlogs"])
    return " ".join(lines) or t["no_results"]


def _certificates(ctx: AuthContext, t: dict[str, Any]) -> str:
    from app.modules.certificates import service as certificates

    c = certificates.mine(ctx)
    today = clock.today().isoformat()
    lines = [
        t["request"](
            r["type_name"], _d(r["requested_at"]), t["status"].get(r["status"], r["status"]),
            _d(r["due_date"]) if r["status"] in certificates.OPEN else "",
            r["status"] in certificates.OPEN and today > r["due_date"],
        )
        for r in c["requests"][:5]
    ] or [t["no_requests"]]  # fmt: skip
    if c.get("no_dues"):
        lines.append(t["dues"]("; ".join(f"{d['what']} {format_inr(d['amount'])}" for d in c["no_dues"])))
    return " ".join(lines)


BUILDERS: dict[str, Callable[[AuthContext, dict[str, Any]], str]] = {
    "fees": _fees,
    "attendance": _attendance,
    "results": _results,
    "certificates": _certificates,
}


def allowed_areas(ctx: AuthContext) -> set[str]:
    """Students: all their own areas. Parents: what the child shares (certificates always). Others: none."""
    kind = ctx.user.get("kind")
    if kind == "student":
        return set(AREAS)
    if kind == "parent":
        from app.modules.parents import service as parents

        try:
            shared = parents.access(parents.child(ctx))
        except AppError:
            return set()
        return {"certificates"} | {a for a in ("fees", "attendance", "results") if shared.get(a)}
    return set()


def excerpts(ctx: AuthContext, question: str, language: str) -> list[dict[str, Any]]:
    """Record excerpts for the areas the question is about and the asker may see; [] for everyone else."""
    wanted = [a for a in areas_asked(question) if a in allowed_areas(ctx)]
    if not wanted:
        return []
    t = T[language]
    document = t["document"](_d(clock.today().isoformat()))
    out = []
    for area in wanted:
        try:
            text = BUILDERS[area](ctx, t)
        except AppError:
            continue  # e.g. no student record yet
        out.append(
            {
                "id": f"record:{area}",
                "category": {"fees": "fees", "certificates": "admissions"}.get(area, "examinations"),
                "title": t[f"{area}_title"],
                "document": document,
                "section": area,
                "text": text,
                "link": LINKS[area],
                "record": area,
                "related": sorted(DOC_CATEGORIES[area]),
                "hint": HINTS[area],
            }
        )
    return out
