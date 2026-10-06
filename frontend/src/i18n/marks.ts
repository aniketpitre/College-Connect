import type { Language } from "../lib/types";

/** Marks and results strings students see. */
export interface MarksStrings {
  title: string;
  internalMarks: string;
  outOf: (n: number) => string;
  absent: string;
  notEntered: string;
  total: string;
  none: string;
  status: Record<string, string>;
  examForms: string;
  formBy: (date: string) => string;
  formClosed: string;
  yourSubjects: string;
  backlog: string;
  submitForm: string;
  formStatus: Record<string, string>;
  lowAttendance: (subjects: string) => string;
  feeDue: (amount: string) => string;
  seatNo: string;
  hallTicket: string;
  papers: string;
  results: string;
  cgpa: string;
  sgpa: string;
  backlogs: string;
  noBacklogs: string;
  outcome: Record<string, string>;
  grade: string;
  download: string;
  askReval: string;
  revalUntil: (d: string) => string;
}

export const MARKS_STRINGS: Record<Language, MarksStrings> = {
  en: {
    title: "Exams & results",
    internalMarks: "Internal marks",
    outOf: (n) => `out of ${n}`,
    absent: "Absent",
    notEntered: "Not entered yet",
    total: "Total",
    none: "Your teachers haven't published any internal marks yet.",
    status: { published: "Published by your teacher", approved: "Approved by the HOD", locked: "Final" },
    examForms: "Exam forms",
    formBy: (d) => `Fill the form by ${d}.`,
    formClosed: "The form is closed. Contact the Exam Cell.",
    yourSubjects: "Your papers",
    backlog: "backlog",
    submitForm: "Submit exam form",
    formStatus: { not_submitted: "Not submitted", submitted: "Submitted, waiting for the Exam Cell", verified: "Verified", rejected: "Not accepted" },
    lowAttendance: (s) => `Attendance below the minimum in ${s}. The Exam Cell decides if you can sit the exam.`,
    feeDue: (a) => `Exam fee due: ${a}. Pay at the accounts counter.`,
    seatNo: "Seat number",
    hallTicket: "Download hall ticket",
    papers: "Paper timetable",
    results: "Results",
    cgpa: "CGPA",
    sgpa: "SGPA",
    backlogs: "Backlogs to clear",
    noBacklogs: "No backlogs.",
    outcome: { pass: "Pass", atkt: "ATKT (backlog)", absent: "Absent" },
    grade: "Grade",
    download: "Download statement (PDF)",
    askReval: "Ask for revaluation",
    revalUntil: (d) => `Revaluation can be asked until ${d}.`,
  },
  hi: {
    title: "परीक्षा और परिणाम",
    internalMarks: "आंतरिक अंक",
    outOf: (n) => `${n} में से`,
    absent: "अनुपस्थित",
    notEntered: "अभी दर्ज नहीं",
    total: "कुल",
    none: "आपके शिक्षकों ने अभी तक कोई आंतरिक अंक प्रकाशित नहीं किए हैं।",
    status: { published: "शिक्षक द्वारा प्रकाशित", approved: "विभागाध्यक्ष द्वारा स्वीकृत", locked: "अंतिम" },
    examForms: "परीक्षा फ़ॉर्म",
    formBy: (d) => `${d} तक फ़ॉर्म भरें।`,
    formClosed: "फ़ॉर्म बंद हो गया है। परीक्षा विभाग से संपर्क करें।",
    yourSubjects: "आपके पेपर",
    backlog: "बैकलॉग",
    submitForm: "परीक्षा फ़ॉर्म जमा करें",
    formStatus: { not_submitted: "जमा नहीं किया", submitted: "जमा किया, परीक्षा विभाग की प्रतीक्षा", verified: "सत्यापित", rejected: "स्वीकार नहीं" },
    lowAttendance: (s) => `${s} में उपस्थिति न्यूनतम से कम है। परीक्षा विभाग तय करेगा कि आप परीक्षा दे सकते हैं या नहीं।`,
    feeDue: (a) => `परीक्षा शुल्क बकाया: ${a}। लेखा काउंटर पर भुगतान करें।`,
    seatNo: "सीट नंबर",
    hallTicket: "हॉल टिकट डाउनलोड करें",
    papers: "पेपर समय सारणी",
    results: "परिणाम",
    cgpa: "CGPA",
    sgpa: "SGPA",
    backlogs: "बाकी बैकलॉग",
    noBacklogs: "कोई बैकलॉग नहीं।",
    outcome: { pass: "उत्तीर्ण", atkt: "ATKT (बैकलॉग)", absent: "अनुपस्थित" },
    grade: "ग्रेड",
    download: "विवरण डाउनलोड करें (PDF)",
    askReval: "पुनर्मूल्यांकन माँगें",
    revalUntil: (d) => `पुनर्मूल्यांकन ${d} तक माँगा जा सकता है।`,
  },
  mr: {
    title: "परीक्षा आणि निकाल",
    internalMarks: "अंतर्गत गुण",
    outOf: (n) => `${n} पैकी`,
    absent: "गैरहजर",
    notEntered: "अजून नोंदवलेले नाहीत",
    total: "एकूण",
    none: "तुमच्या शिक्षकांनी अजून कोणतेही अंतर्गत गुण प्रसिद्ध केलेले नाहीत.",
    status: { published: "शिक्षकांनी प्रसिद्ध केले", approved: "विभागप्रमुखांनी मंजूर केले", locked: "अंतिम" },
    examForms: "परीक्षा अर्ज",
    formBy: (d) => `${d} पर्यंत अर्ज भरा.`,
    formClosed: "अर्ज बंद झाला आहे. परीक्षा विभागाशी संपर्क साधा.",
    yourSubjects: "तुमचे पेपर",
    backlog: "बॅकलॉग",
    submitForm: "परीक्षा अर्ज सादर करा",
    formStatus: { not_submitted: "सादर केलेला नाही", submitted: "सादर केला, परीक्षा विभागाची प्रतीक्षा", verified: "पडताळला", rejected: "स्वीकारला नाही" },
    lowAttendance: (s) => `${s} मध्ये हजेरी किमानपेक्षा कमी आहे. परीक्षेला बसता येईल का हे परीक्षा विभाग ठरवेल.`,
    feeDue: (a) => `परीक्षा शुल्क बाकी: ${a}. लेखा काउंटरवर भरा.`,
    seatNo: "आसन क्रमांक",
    hallTicket: "हॉल तिकीट डाउनलोड करा",
    papers: "पेपर वेळापत्रक",
    results: "निकाल",
    cgpa: "CGPA",
    sgpa: "SGPA",
    backlogs: "बाकी बॅकलॉग",
    noBacklogs: "कोणताही बॅकलॉग नाही.",
    outcome: { pass: "उत्तीर्ण", atkt: "ATKT (बॅकलॉग)", absent: "गैरहजर" },
    grade: "श्रेणी",
    download: "निवेदन डाउनलोड करा (PDF)",
    askReval: "पुनर्मूल्यांकन मागा",
    revalUntil: (d) => `पुनर्मूल्यांकन ${d} पर्यंत मागता येईल.`,
  },
};
