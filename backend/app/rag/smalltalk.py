"""Friendly replies that need no AI and no documents: greetings, thanks and "what can you do?".

They are answered at once (no search, no AI call) and are not logged as unanswered questions.
"""

import re

_GREETING = {
    "hi", "hii", "hello", "hey", "hey there", "hello there", "good morning", "good afternoon", "good evening",
    "namaste", "namaskar", "namaskaar", "नमस्ते", "नमस्कार", "हाय", "हॅलो", "हेलो", "सुप्रभात", "शुभ प्रभात",
}  # fmt: skip
_THANKS = {
    "thanks", "thank you", "thank you so much", "thanks a lot", "thx", "ty", "ok thanks", "okay thanks",
    "ok thank you", "great thanks", "dhanyavad", "dhanyawad", "shukriya", "धन्यवाद", "शुक्रिया", "आभार",
    "बहुत धन्यवाद", "खूप धन्यवाद", "thanks!",
}  # fmt: skip
_HELP = {
    "help", "what can you do", "who are you", "what are you", "how can you help", "what can i ask",
    "तुम कौन हो", "आप कौन हैं", "आप क्या कर सकते हैं", "मदद", "तू कोण आहेस", "तुम्ही कोण आहात",
    "तुम्ही काय करू शकता", "मदत",
}  # fmt: skip

EXAMPLES = {
    "en": "For example: “When is the last date to pay fees?”, “When do exams start?” or “How much fee do I still owe?”",
    "hi": "जैसे: “फीस भरने की आखिरी तारीख क्या है?”, “परीक्षा कब शुरू होगी?” या “मेरी कितनी फीस बाकी है?”",
    "mr": "उदा.: “फी भरण्याची शेवटची तारीख कोणती?”, “परीक्षा कधी सुरू होणार?” किंवा “माझी किती फी बाकी आहे?”",
}
CAN_HELP = {
    "en": "I can help with fees, exams and results, attendance, certificates, admissions, scholarships, "
    "the library, hostel, placements and college notices.",
    "hi": "मैं फीस, परीक्षा और परिणाम, उपस्थिति, प्रमाणपत्र, प्रवेश, छात्रवृत्ति, पुस्तकालय, छात्रावास, "
    "प्लेसमेंट और कॉलेज की सूचनाओं में मदद कर सकता हूँ।",
    "mr": "मी फी, परीक्षा आणि निकाल, उपस्थिती, प्रमाणपत्रे, प्रवेश, शिष्यवृत्ती, ग्रंथालय, वसतिगृह, "
    "प्लेसमेंट आणि महाविद्यालयाच्या सूचनांबद्दल मदत करू शकतो.",
}
REPLIES = {
    "greeting": {
        "en": "Hello! 👋 I'm CollegeConnect AI, your college help desk.",
        "hi": "नमस्ते! 👋 मैं CollegeConnect AI हूँ, आपके कॉलेज का हेल्प डेस्क।",
        "mr": "नमस्कार! 👋 मी CollegeConnect AI, तुमच्या महाविद्यालयाचा हेल्प डेस्क.",
    },
    "thanks": {
        "en": "You're welcome! 😊 Happy to help. Ask me anytime.",
        "hi": "आपका स्वागत है! 😊 मदद करके खुशी हुई। कभी भी पूछिए।",
        "mr": "तुमचे स्वागत आहे! 😊 मदत करून आनंद झाला. कधीही विचारा.",
    },
    "help": {
        "en": "I'm CollegeConnect AI, the college's help desk. I answer from the college's official documents "
        "and your own record.",
        "hi": "मैं CollegeConnect AI हूँ, कॉलेज का हेल्प डेस्क। मैं कॉलेज के आधिकारिक दस्तावेज़ों और आपके अपने रिकॉर्ड से उत्तर देता हूँ।",
        "mr": "मी CollegeConnect AI, महाविद्यालयाचा हेल्प डेस्क. मी महाविद्यालयाच्या अधिकृत कागदपत्रांतून आणि "
        "तुमच्या स्वतःच्या नोंदींमधून उत्तर देतो.",
    },
}


def _norm(text: str) -> str:
    text = re.sub(r"[!?.,।🙏😊👋🙂:)]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def kind(question: str) -> str | None:
    q = _norm(question)
    for name, phrases in (("greeting", _GREETING), ("thanks", _THANKS), ("help", _HELP)):
        if q in phrases:
            return name
    # "hi there, good morning" / "hello sir": a greeting word plus at most two short words.
    words = q.split()
    if 1 < len(words) <= 3 and words[0] in {"hi", "hello", "hey", "namaste", "namaskar", "नमस्ते", "नमस्कार"}:
        return "greeting"
    return None


def reply(question: str, language: str) -> str | None:
    """A friendly answer for small talk, or None if this is a real question."""
    k = kind(question)
    if k is None:
        return None
    if k == "thanks":
        return REPLIES[k][language]
    return f"{REPLIES[k][language]} {CAN_HELP[language]}\n\n{EXAMPLES[language]}"
