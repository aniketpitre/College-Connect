import type { Language } from "../lib/types";

/** The student's scholarship checker, in English, Hindi and Marathi. */
export interface ScholarshipStrings {
  title: string;
  intro: string;
  income: string;
  incomeHint: string;
  save: string;
  declared: (amount: string) => string;
  statuses: Record<string, string>;
  why: string;
  notMet: Record<string, (p: Record<string, unknown>) => string>;
  unknown: Record<string, string>;
  upload: string;
  uploadLink: string;
  apply: (portal: string) => string;
  applied: string;
  disclaimer: string;
}

const list = (v: unknown) => (Array.isArray(v) ? v.join(", ") : String(v ?? ""));
const rupees = (v: unknown) => `₹${Number(v).toLocaleString("en-IN")}`;

export const SCHOLARSHIP_STRINGS: Record<Language, ScholarshipStrings> = {
  en: {
    title: "Scholarships",
    intro: "Which scholarships you may qualify for, from your record. Check the rules on the portal before you apply.",
    income: "Family income a year (₹)",
    incomeHint: "As on your income certificate. Used only for this guide.",
    save: "Save",
    declared: (a) => `Family income you gave: ${a}`,
    statuses: {
      likely: "You may qualify",
      missing_documents: "Upload documents first",
      check: "Need more information",
      applied: "Applied",
      not_eligible: "Not for you",
    },
    why: "Why",
    notMet: {
      category: (p) => `Only for these categories: ${list(p.allowed)}`,
      income: (p) => `Family income must be at most ${rupees(p.limit)}`,
      domicile: (p) => `Only for students from ${String(p.state)}`,
      attendance: (p) => `Needs at least ${String(p.minimum)}% attendance`,
      percentage: (p) => `Needs at least ${String(p.minimum)}% in the previous exam`,
      gender: () => "Only for girls",
      year: (p) => `Only for year ${list(p.years)}`,
    },
    unknown: {
      category: "Your category is not in your record",
      income: "Enter your family income above",
      domicile: "Your state is not in your record",
      percentage: "Your previous exam percentage is not in your record",
      gender: "Your gender is not in your record",
      year: "Your year of study is not in your record",
    },
    upload: "Documents to upload:",
    uploadLink: "Upload on My profile",
    apply: (portal) => `Apply on ${portal}`,
    applied: "The college has your application: status",
    disclaimer: "This is a guide, not a decision. The scholarship portal decides.",
  },
  hi: {
    title: "छात्रवृत्ति",
    intro: "आपके रिकॉर्ड के आधार पर आप किन छात्रवृत्तियों के लिए पात्र हो सकते हैं। आवेदन से पहले पोर्टल पर नियम जाँच लें।",
    income: "परिवार की वार्षिक आय (₹)",
    incomeHint: "आपके आय प्रमाणपत्र के अनुसार। केवल इस मार्गदर्शन के लिए।",
    save: "सहेजें",
    declared: (a) => `आपके द्वारा बताई गई पारिवारिक आय: ${a}`,
    statuses: {
      likely: "आप पात्र हो सकते हैं",
      missing_documents: "पहले दस्तावेज़ अपलोड करें",
      check: "और जानकारी चाहिए",
      applied: "आवेदन किया",
      not_eligible: "आपके लिए नहीं",
    },
    why: "कारण",
    notMet: {
      category: (p) => `केवल इन श्रेणियों के लिए: ${list(p.allowed)}`,
      income: (p) => `पारिवारिक आय अधिकतम ${rupees(p.limit)} होनी चाहिए`,
      domicile: (p) => `केवल ${String(p.state)} के छात्रों के लिए`,
      attendance: (p) => `कम से कम ${String(p.minimum)}% उपस्थिति चाहिए`,
      percentage: (p) => `पिछली परीक्षा में कम से कम ${String(p.minimum)}% चाहिए`,
      gender: () => "केवल छात्राओं के लिए",
      year: (p) => `केवल वर्ष ${list(p.years)} के लिए`,
    },
    unknown: {
      category: "आपकी श्रेणी रिकॉर्ड में नहीं है",
      income: "ऊपर अपनी पारिवारिक आय लिखें",
      domicile: "आपका राज्य रिकॉर्ड में नहीं है",
      percentage: "पिछली परीक्षा का प्रतिशत रिकॉर्ड में नहीं है",
      gender: "आपका लिंग रिकॉर्ड में नहीं है",
      year: "आपका अध्ययन वर्ष रिकॉर्ड में नहीं है",
    },
    upload: "अपलोड करने के दस्तावेज़:",
    uploadLink: "मेरी प्रोफ़ाइल पर अपलोड करें",
    apply: (portal) => `${portal} पर आवेदन करें`,
    applied: "कॉलेज के पास आपका आवेदन है: स्थिति",
    disclaimer: "यह केवल मार्गदर्शन है, निर्णय नहीं। निर्णय छात्रवृत्ति पोर्टल करता है।",
  },
  mr: {
    title: "शिष्यवृत्ती",
    intro: "तुमच्या नोंदीनुसार तुम्ही कोणत्या शिष्यवृत्तींसाठी पात्र ठरू शकता. अर्ज करण्यापूर्वी पोर्टलवर नियम तपासा.",
    income: "कुटुंबाचे वार्षिक उत्पन्न (₹)",
    incomeHint: "तुमच्या उत्पन्नाच्या दाखल्यानुसार. फक्त या मार्गदर्शनासाठी.",
    save: "जतन करा",
    declared: (a) => `तुम्ही दिलेले कौटुंबिक उत्पन्न: ${a}`,
    statuses: {
      likely: "तुम्ही पात्र ठरू शकता",
      missing_documents: "आधी कागदपत्रे अपलोड करा",
      check: "अधिक माहिती हवी",
      applied: "अर्ज केला",
      not_eligible: "तुमच्यासाठी नाही",
    },
    why: "कारण",
    notMet: {
      category: (p) => `फक्त या प्रवर्गांसाठी: ${list(p.allowed)}`,
      income: (p) => `कौटुंबिक उत्पन्न जास्तीत जास्त ${rupees(p.limit)} असावे`,
      domicile: (p) => `फक्त ${String(p.state)} मधील विद्यार्थ्यांसाठी`,
      attendance: (p) => `किमान ${String(p.minimum)}% उपस्थिती हवी`,
      percentage: (p) => `मागील परीक्षेत किमान ${String(p.minimum)}% हवेत`,
      gender: () => "फक्त विद्यार्थिनींसाठी",
      year: (p) => `फक्त वर्ष ${list(p.years)} साठी`,
    },
    unknown: {
      category: "तुमचा प्रवर्ग नोंदीत नाही",
      income: "वर तुमचे कौटुंबिक उत्पन्न लिहा",
      domicile: "तुमचे राज्य नोंदीत नाही",
      percentage: "मागील परीक्षेची टक्केवारी नोंदीत नाही",
      gender: "तुमचे लिंग नोंदीत नाही",
      year: "तुमचे शिक्षण वर्ष नोंदीत नाही",
    },
    upload: "अपलोड करायची कागदपत्रे:",
    uploadLink: "माझ्या प्रोफाइलवर अपलोड करा",
    apply: (portal) => `${portal} वर अर्ज करा`,
    applied: "कॉलेजकडे तुमचा अर्ज आहे: स्थिती",
    disclaimer: "हे केवळ मार्गदर्शन आहे, निर्णय नाही. निर्णय शिष्यवृत्ती पोर्टल घेते.",
  },
};
