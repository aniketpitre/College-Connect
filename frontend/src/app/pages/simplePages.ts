import type { Language } from "../../lib/types";

type Strings = Record<Language, { title: string; body: string; back: string }>;

type VerifyStrings = Record<
  Language,
  {
    title: string;
    checking: string;
    genuine: string;
    cancelled: string;
    notFound: string;
    receipt: string;
    date: string;
    amount: string;
    student: string;
    year: string;
    issuedBy: string;
    cancelledOn: string;
    back: string;
    genuineCert: string;
    revokedCert: string;
    certNo: string;
    document: string;
  }
>;

/** Public Verify page (scanned from a receipt's QR code). */
export const VERIFY: VerifyStrings = {
  en: {
    title: "Check a receipt or certificate",
    checking: "Checking…",
    genuine: "Genuine receipt",
    cancelled: "This receipt was cancelled",
    notFound: "No receipt matches this code. Check the code, or ask the college office.",
    receipt: "Receipt no.",
    date: "Date",
    amount: "Amount",
    student: "Student",
    year: "Academic year",
    issuedBy: "Issued by",
    cancelledOn: "Cancelled on",
    back: "Back to the help desk",
    genuineCert: "Genuine certificate",
    revokedCert: "This certificate was withdrawn",
    certNo: "Certificate no.",
    document: "Document",
  },
  hi: {
    title: "रसीद या प्रमाणपत्र जांचें",
    checking: "जांच हो रही है…",
    genuine: "असली रसीद",
    cancelled: "यह रसीद रद्द कर दी गई है",
    notFound: "इस कोड से कोई रसीद नहीं मिली। कोड जांचें या कॉलेज कार्यालय से पूछें।",
    receipt: "रसीद क्रमांक",
    date: "दिनांक",
    amount: "राशि",
    student: "छात्र",
    year: "शैक्षणिक वर्ष",
    issuedBy: "जारीकर्ता",
    cancelledOn: "रद्द करने की तिथि",
    back: "हेल्प डेस्क पर वापस जाएं",
    genuineCert: "असली प्रमाणपत्र",
    revokedCert: "यह प्रमाणपत्र वापस ले लिया गया है",
    certNo: "प्रमाणपत्र क्रमांक",
    document: "दस्तावेज़",
  },
  mr: {
    title: "पावती किंवा प्रमाणपत्र पडताळा",
    checking: "तपासत आहे…",
    genuine: "खरी पावती",
    cancelled: "ही पावती रद्द केली आहे",
    notFound: "या कोडशी जुळणारी पावती सापडली नाही. कोड तपासा किंवा महाविद्यालय कार्यालयात विचारा.",
    receipt: "पावती क्रमांक",
    date: "दिनांक",
    amount: "रक्कम",
    student: "विद्यार्थी",
    year: "शैक्षणिक वर्ष",
    issuedBy: "देणारे",
    cancelledOn: "रद्द केल्याचा दिनांक",
    back: "हेल्प डेस्कवर परत जा",
    genuineCert: "खरे प्रमाणपत्र",
    revokedCert: "हे प्रमाणपत्र मागे घेतले आहे",
    certNo: "प्रमाणपत्र क्रमांक",
    document: "दस्तऐवज",
  },
};

export const NOT_FOUND: Strings = {
  en: { title: "Page not found", body: "This address doesn't exist.", back: "Go to the help desk" },
  hi: { title: "पेज नहीं मिला", body: "यह पता मौजूद नहीं है।", back: "हेल्प डेस्क पर जाएं" },
  mr: { title: "पान सापडले नाही", body: "हा पत्ता अस्तित्वात नाही.", back: "हेल्प डेस्कवर जा" },
};

export function browserLanguage(): Language {
  const lang = (typeof navigator !== "undefined" ? navigator.language : "en").slice(0, 2);
  return lang === "hi" || lang === "mr" ? lang : "en";
}
