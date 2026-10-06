import type { Language } from "../lib/types";

/** Parent sign-in, the child switcher, and the student's "what my parents see" controls. */
export interface ParentStrings {
  parent: string;
  mobile: string;
  mobileHint: string;
  sendCode: string;
  sending: string;
  codeSent: string;
  code: string;
  verify: string;
  codeWrong: string;
  resend: string;
  usePassword: string;
  useCode: string;
  viewing: string;
  noChildren: string;
  sharingTitle: string;
  sharingIntro: string;
  areas: { fees: string; attendance: string; results: string };
  minorNote: string;
  noParents: string;
  linked: (names: string) => string;
  save: string;
  saved: string;
}

export const PARENT_STRINGS: Record<Language, ParentStrings> = {
  en: {
    parent: "Parent",
    mobile: "Mobile number",
    mobileHint: "The number you gave the college office",
    sendCode: "Send sign-in code",
    sending: "Sending…",
    codeSent: "If this number is registered, a 6-digit code has been sent to your email. It works for 10 minutes.",
    code: "Sign-in code",
    verify: "Sign in",
    codeWrong: "That code is wrong or has expired. Ask for a new one.",
    resend: "Send a new code",
    usePassword: "Sign in with a password instead",
    useCode: "Sign in with a code instead",
    viewing: "Showing",
    noChildren: "No student is linked to this account yet. Please contact the college office.",
    sharingTitle: "What my parents can see",
    sharingIntro: "Parents linked by the college office can see your timetable, notices and certificates. Choose what else they see.",
    areas: { fees: "Fees and receipts", attendance: "Attendance", results: "Marks and results" },
    minorNote: "You are under 18, so your parents can see everything (their consent is on record with the college).",
    noParents: "No parent account is linked to you.",
    linked: (names) => `Linked: ${names}`,
    save: "Save",
    saved: "Saved.",
  },
  hi: {
    parent: "अभिभावक",
    mobile: "मोबाइल नंबर",
    mobileHint: "वही नंबर जो आपने कॉलेज कार्यालय को दिया है",
    sendCode: "साइन-इन कोड भेजें",
    sending: "भेजा जा रहा है…",
    codeSent: "यदि यह नंबर पंजीकृत है, तो आपके ईमेल पर 6 अंकों का कोड भेजा गया है। यह 10 मिनट तक चलेगा।",
    code: "साइन-इन कोड",
    verify: "साइन इन करें",
    codeWrong: "कोड गलत है या उसकी समय-सीमा समाप्त हो गई है। नया कोड मंगाएँ।",
    resend: "नया कोड भेजें",
    usePassword: "पासवर्ड से साइन इन करें",
    useCode: "कोड से साइन इन करें",
    viewing: "दिखाया जा रहा है",
    noChildren: "इस खाते से अभी कोई छात्र जुड़ा नहीं है। कृपया कॉलेज कार्यालय से संपर्क करें।",
    sharingTitle: "मेरे अभिभावक क्या देख सकते हैं",
    sharingIntro: "कॉलेज कार्यालय द्वारा जोड़े गए अभिभावक आपकी समय-सारिणी, सूचनाएँ और प्रमाणपत्र देख सकते हैं। चुनें कि वे और क्या देखें।",
    areas: { fees: "फ़ीस और रसीदें", attendance: "उपस्थिति", results: "अंक और परिणाम" },
    minorNote: "आपकी आयु 18 वर्ष से कम है, इसलिए आपके अभिभावक सब कुछ देख सकते हैं (उनकी सहमति कॉलेज के पास दर्ज है)।",
    noParents: "आपसे कोई अभिभावक खाता जुड़ा नहीं है।",
    linked: (names) => `जुड़े हुए: ${names}`,
    save: "सहेजें",
    saved: "सहेजा गया।",
  },
  mr: {
    parent: "पालक",
    mobile: "मोबाइल नंबर",
    mobileHint: "तुम्ही कॉलेज कार्यालयाला दिलेला नंबर",
    sendCode: "साइन-इन कोड पाठवा",
    sending: "पाठवत आहे…",
    codeSent: "हा नंबर नोंदणीकृत असल्यास तुमच्या ईमेलवर 6 अंकी कोड पाठवला आहे. तो 10 मिनिटे चालेल.",
    code: "साइन-इन कोड",
    verify: "साइन इन करा",
    codeWrong: "कोड चुकीचा आहे किंवा त्याची मुदत संपली आहे. नवीन कोड मागवा.",
    resend: "नवीन कोड पाठवा",
    usePassword: "पासवर्डने साइन इन करा",
    useCode: "कोडने साइन इन करा",
    viewing: "दाखवत आहे",
    noChildren: "या खात्याशी अद्याप कोणताही विद्यार्थी जोडलेला नाही. कृपया कॉलेज कार्यालयाशी संपर्क साधा.",
    sharingTitle: "माझे पालक काय पाहू शकतात",
    sharingIntro: "कॉलेज कार्यालयाने जोडलेले पालक तुमचे वेळापत्रक, सूचना आणि प्रमाणपत्रे पाहू शकतात. ते आणखी काय पाहतील ते निवडा.",
    areas: { fees: "फी आणि पावत्या", attendance: "उपस्थिती", results: "गुण आणि निकाल" },
    minorNote: "तुमचे वय 18 पेक्षा कमी आहे, त्यामुळे तुमचे पालक सर्व काही पाहू शकतात (त्यांची संमती कॉलेजकडे नोंदलेली आहे).",
    noParents: "तुमच्याशी कोणतेही पालक खाते जोडलेले नाही.",
    linked: (names) => `जोडलेले: ${names}`,
    save: "जतन करा",
    saved: "जतन केले.",
  },
};
