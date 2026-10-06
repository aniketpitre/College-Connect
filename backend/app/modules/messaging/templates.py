# ruff: noqa: E501  (message texts read better on one line)
"""
Message templates in English, Hindi and Marathi.

One text per template works as an SMS, a WhatsApp message and an email body, and reads right
for the student and for their parents (it names the student). SMS in India must match a
DLT-approved template, so each key below maps to a provider template id set in the environment
(SMS_TEMPLATE_<KEY>, WHATSAPP_TEMPLATE_<KEY>); the variables are sent in the order of `VARS`.
"""

from typing import Any

# The order of each template's variables (for SMS/WhatsApp providers' numbered placeholders).
VARS: dict[str, tuple[str, ...]] = {
    "otp": ("code",),
    "attendance_critical": ("student", "code", "pct", "minimum", "n"),
    "attendance_warning": ("student", "code", "pct", "minimum", "n"),
    "fee_due": ("student", "amount", "label", "date"),
    "fee_overdue": ("student", "amount"),
    "results_published": ("student", "exam"),
    "certificate_ready": ("student", "certificate", "number"),
    "application_returned": ("student", "reason"),
    "admission_offer": ("student", "programme", "date"),
    "admission_confirmed": ("student", "programme", "prn"),
    "library_overdue": ("student", "title", "date"),
    "library_ready": ("student", "title", "date"),
    "outpass_approved": ("student", "place", "from", "to"),
    "placement_selected": ("student", "company", "role"),
    "grievance_replied": ("student", "number"),
    "grievance_resolved": ("student", "number"),
}

# Which part of the student's record each message is about: parents get it only if shared.
# "private": only the student, never their parents (grievances).
AREA: dict[str, str | None] = {
    "otp": None,
    "attendance_critical": "attendance",
    "attendance_warning": "attendance",
    "fee_due": "fees",
    "fee_overdue": "fees",
    "results_published": "results",
    "certificate_ready": None,
    "application_returned": None,
    "admission_offer": None,
    "admission_confirmed": None,
    "library_overdue": None,
    "library_ready": None,
    "outpass_approved": None,
    "placement_selected": None,
    "grievance_replied": "private",
    "grievance_resolved": "private",
}

LABELS = {
    "otp": "Sign-in code",
    "attendance_critical": "Attendance below minimum",
    "attendance_warning": "Attendance warning",
    "fee_due": "Fee due soon",
    "fee_overdue": "Fee overdue",
    "results_published": "Results published",
    "certificate_ready": "Certificate ready",
    "application_returned": "Application returned",
    "admission_offer": "Admission offered",
    "admission_confirmed": "Admission confirmed",
    "library_overdue": "Library book overdue",
    "library_ready": "Reserved book ready",
    "outpass_approved": "Hostel out-pass approved",
    "placement_selected": "Placement offer",
    "grievance_replied": "Reply to your grievance",
    "grievance_resolved": "Grievance resolved",
}

TEXT: dict[str, dict[str, tuple[str, str]]] = {
    "otp": {
        "en": (
            "{code} is your CollegeConnect sign-in code",
            "{code} is your CollegeConnect sign-in code. It works for 10 minutes. Never share it.",
        ),
        "hi": (
            "{code} आपका CollegeConnect साइन-इन कोड है",
            "{code} आपका CollegeConnect साइन-इन कोड है। यह 10 मिनट तक चलेगा। इसे किसी से साझा न करें।",
        ),
        "mr": (
            "{code} हा तुमचा CollegeConnect साइन-इन कोड आहे",
            "{code} हा तुमचा CollegeConnect साइन-इन कोड आहे. तो 10 मिनिटे चालेल. तो कोणालाही सांगू नका.",
        ),
    },
    "attendance_critical": {
        "en": (
            "Low attendance: {code} {pct}%",
            "Attendance of {student} in {code} is {pct}%, below the minimum of {minimum}%. Attend the next {n} lectures to reach it.",
        ),
        "hi": (
            "कम उपस्थिति: {code} {pct}%",
            "{student} की {code} में उपस्थिति {pct}% है, जो न्यूनतम {minimum}% से कम है। इसे पूरा करने के लिए अगले {n} व्याख्यानों में उपस्थित रहें।",
        ),
        "mr": (
            "कमी उपस्थिती: {code} {pct}%",
            "{student} यांची {code} मधील उपस्थिती {pct}% आहे, किमान {minimum}% पेक्षा कमी. ती गाठण्यासाठी पुढील {n} तासिकांना उपस्थित राहा.",
        ),
    },
    "attendance_warning": {
        "en": (
            "Attendance warning: {code} {pct}%",
            "Attendance of {student} in {code} is {pct}% (minimum {minimum}%). Only {n} more lectures can be missed.",
        ),
        "hi": (
            "उपस्थिति चेतावनी: {code} {pct}%",
            "{student} की {code} में उपस्थिति {pct}% है (न्यूनतम {minimum}%)। अब केवल {n} व्याख्यान छोड़े जा सकते हैं।",
        ),
        "mr": (
            "उपस्थिती इशारा: {code} {pct}%",
            "{student} यांची {code} मधील उपस्थिती {pct}% आहे (किमान {minimum}%). आता फक्त {n} तासिका चुकवता येतील.",
        ),
    },
    "fee_due": {
        "en": (
            "Fee due on {date}",
            "{label} of {amount} for {student} is due on {date}. Pay online in CollegeConnect or at the college counter.",
        ),
        "hi": (
            "{date} को फ़ीस देय",
            "{student} की {label} {amount} {date} को देय है। CollegeConnect पर ऑनलाइन या कॉलेज काउंटर पर भुगतान करें।",
        ),
        "mr": (
            "{date} रोजी शुल्क देय",
            "{student} यांचा {label} {amount} {date} रोजी देय आहे. CollegeConnect वर ऑनलाइन किंवा कॉलेज काउंटरवर भरा.",
        ),
    },
    "fee_overdue": {
        "en": (
            "Fee overdue: {amount}",
            "{amount} of fees for {student} is overdue. Please pay online in CollegeConnect or at the college counter.",
        ),
        "hi": (
            "बकाया फ़ीस: {amount}",
            "{student} की {amount} फ़ीस बकाया है। कृपया CollegeConnect पर ऑनलाइन या कॉलेज काउंटर पर भुगतान करें।",
        ),
        "mr": (
            "थकित शुल्क: {amount}",
            "{student} यांचे {amount} शुल्क थकित आहे. कृपया CollegeConnect वर ऑनलाइन किंवा कॉलेज काउंटरवर भरा.",
        ),
    },
    "results_published": {
        "en": (
            "Results published: {exam}",
            "Results of {exam} for {student} are out. See them in CollegeConnect (Exams & results).",
        ),
        "hi": (
            "परिणाम घोषित: {exam}",
            "{student} का {exam} का परिणाम आ गया है। CollegeConnect (परीक्षा और परिणाम) में देखें।",
        ),
        "mr": (
            "निकाल जाहीर: {exam}",
            "{student} यांचा {exam} चा निकाल लागला आहे. CollegeConnect (परीक्षा आणि निकाल) मध्ये पाहा.",
        ),
    },
    "certificate_ready": {
        "en": (
            "{certificate} ready",
            "The {certificate} ({number}) for {student} is ready. Download it in CollegeConnect or collect the signed copy at the office.",
        ),
        "hi": (
            "{certificate} तैयार",
            "{student} का {certificate} ({number}) तैयार है। CollegeConnect से डाउनलोड करें या कार्यालय से हस्ताक्षरित प्रति लें।",
        ),
        "mr": (
            "{certificate} तयार",
            "{student} यांचे {certificate} ({number}) तयार आहे. CollegeConnect मधून डाउनलोड करा किंवा कार्यालयातून स्वाक्षरी केलेली प्रत घ्या.",
        ),
    },
}


TEXT.update(
    {
        "application_returned": {
            "en": (
                "Your application needs a correction",
                "The admission application of {student} was returned: {reason}. Sign in at CollegeConnect (Apply), correct it and submit again.",
            ),
            "hi": (
                "आपके आवेदन में सुधार चाहिए",
                "{student} का प्रवेश आवेदन लौटाया गया: {reason}। CollegeConnect (आवेदन) पर साइन इन करें, सुधार करें और फिर से जमा करें।",
            ),
            "mr": (
                "तुमच्या अर्जात दुरुस्ती हवी",
                "{student} यांचा प्रवेश अर्ज परत केला: {reason}. CollegeConnect (अर्ज) वर साइन इन करा, दुरुस्ती करा आणि पुन्हा सादर करा.",
            ),
        },
        "admission_offer": {
            "en": (
                "Admission offered: {programme}",
                "{student} is offered admission to {programme}. Come to the college office with the original documents and fees by {date} to confirm.",
            ),
            "hi": (
                "प्रवेश का प्रस्ताव: {programme}",
                "{student} को {programme} में प्रवेश का प्रस्ताव मिला है। पुष्टि के लिए {date} तक मूल दस्तावेज़ और फ़ीस लेकर कॉलेज कार्यालय आएँ।",
            ),
            "mr": (
                "प्रवेशाची ऑफर: {programme}",
                "{student} यांना {programme} मध्ये प्रवेशाची ऑफर आहे. निश्चितीसाठी {date} पर्यंत मूळ कागदपत्रे आणि शुल्क घेऊन कॉलेज कार्यालयात या.",
            ),
        },
        "admission_confirmed": {
            "en": (
                "Admission confirmed: {programme}",
                "Admission of {student} to {programme} is confirmed. PRN: {prn}. Sign in to CollegeConnect as a student with the PRN and the temporary password on the admission slip.",
            ),
            "hi": (
                "प्रवेश की पुष्टि: {programme}",
                "{student} का {programme} में प्रवेश पक्का हो गया है। PRN: {prn}। प्रवेश पर्ची पर दिए अस्थायी पासवर्ड और PRN से CollegeConnect में छात्र के रूप में साइन इन करें।",
            ),
            "mr": (
                "प्रवेश निश्चित: {programme}",
                "{student} यांचा {programme} मधील प्रवेश निश्चित झाला. PRN: {prn}. प्रवेश पावतीवरील तात्पुरता पासवर्ड आणि PRN ने CollegeConnect मध्ये विद्यार्थी म्हणून साइन इन करा.",
            ),
        },
    }
)


TEXT.update(
    {
        "library_overdue": {
            "en": (
                "Library book overdue: {title}",
                "{title}, borrowed by {student}, was due back on {date}. A fine is charged for every day late; please return it to the library.",
            ),
            "hi": (
                "पुस्तक लौटाने में देर: {title}",
                "{student} द्वारा ली गई पुस्तक {title} {date} को लौटानी थी। हर दिन की देरी पर जुर्माना लगता है; कृपया इसे पुस्तकालय में लौटाएँ।",
            ),
            "mr": (
                "पुस्तक परत करण्यास उशीर: {title}",
                "{student} यांनी घेतलेले {title} पुस्तक {date} रोजी परत करायचे होते. प्रत्येक दिवसाच्या उशिराला दंड लागतो; कृपया ते ग्रंथालयात परत करा.",
            ),
        },
        "library_ready": {
            "en": (
                "Your reserved book is ready: {title}",
                "{title}, reserved by {student}, is kept at the library counter until {date}.",
            ),
            "hi": (
                "आरक्षित पुस्तक तैयार: {title}",
                "{student} द्वारा आरक्षित पुस्तक {title} {date} तक पुस्तकालय काउंटर पर रखी है।",
            ),
            "mr": (
                "राखीव पुस्तक तयार: {title}",
                "{student} यांनी राखीव केलेले {title} पुस्तक {date} पर्यंत ग्रंथालय काउंटरवर ठेवले आहे.",
            ),
        },
    }
)

TEXT["outpass_approved"] = {
    "en": ("Hostel out-pass approved", "Out-pass approved for {student}: to {place}, leaving {from}, back by {to}."),
    "hi": ("हॉस्टल आउट-पास स्वीकृत", "{student} का आउट-पास स्वीकृत: {place} के लिए, {from} को जाना, {to} तक लौटना।"),
    "mr": ("वसतिगृह आउट-पास मंजूर", "{student} यांचा आउट-पास मंजूर: {place} साठी, {from} ला जाणे, {to} पर्यंत परत येणे."),
}

TEXT["placement_selected"] = {
    "en": (
        "Selected by {company}",
        "Congratulations! {student} has been selected by {company} as {role}. The placement cell will share the offer details.",
    ),
    "hi": (
        "{company} द्वारा चयन",
        "बधाई! {student} का {company} में {role} पद के लिए चयन हुआ है। प्लेसमेंट सेल ऑफ़र का विवरण देगा।",
    ),
    "mr": (
        "{company} कडून निवड",
        "अभिनंदन! {student} यांची {company} मध्ये {role} पदासाठी निवड झाली आहे. प्लेसमेंट सेल ऑफरचा तपशील देईल.",
    ),
}

TEXT["grievance_replied"] = {
    "en": (
        "Reply to grievance {number}",
        "The college has replied to your grievance {number}. Open CollegeConnect → Grievances to read it.",
    ),
    "hi": (
        "शिकायत {number} पर उत्तर",
        "कॉलेज ने आपकी शिकायत {number} पर उत्तर दिया है। पढ़ने के लिए CollegeConnect → शिकायतें खोलें।",
    ),
    "mr": (
        "तक्रार {number} वर उत्तर",
        "कॉलेजने तुमच्या तक्रार {number} वर उत्तर दिले आहे. वाचण्यासाठी CollegeConnect → तक्रारी उघडा.",
    ),
}

TEXT["grievance_resolved"] = {
    "en": (
        "Grievance {number} resolved",
        "Your grievance {number} has been resolved. Please open CollegeConnect → Grievances and tell us if you are satisfied.",
    ),
    "hi": (
        "शिकायत {number} का समाधान",
        "आपकी शिकायत {number} का समाधान कर दिया गया है। कृपया CollegeConnect → शिकायतें खोलकर बताएँ कि आप संतुष्ट हैं या नहीं।",
    ),
    "mr": (
        "तक्रार {number} चे निवारण",
        "तुमच्या तक्रार {number} चे निवारण झाले आहे. कृपया CollegeConnect → तक्रारी उघडून तुम्ही समाधानी आहात का ते सांगा.",
    ),
}


def render(key: str, language: str | None, params: dict[str, Any]) -> tuple[str, str]:
    """(subject, text) in the person's language (English if unknown)."""
    subject, text = TEXT[key].get(language or "en", TEXT[key]["en"])
    return subject.format(**params), text.format(**params)


def ordered(key: str, params: dict[str, Any]) -> list[str]:
    return [str(params[v]) for v in VARS[key]]
