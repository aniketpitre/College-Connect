import type { Language } from "../lib/types";

/** "How the college reaches me" on My account (students and parents see it in their language). */
export interface MessageStrings {
  title: string;
  intro: string;
  notSetUp: string;
  noAddress: string;
  save: string;
  saved: string;
}

export const MESSAGE_STRINGS: Record<Language, MessageStrings> = {
  en: {
    title: "Messages from the college",
    intro: "Fee reminders, attendance alerts, results and certificates. Sign-in codes are always sent.",
    notSetUp: "not set up by the college yet",
    noAddress: "no number or email on record",
    save: "Save",
    saved: "Saved.",
  },
  hi: {
    title: "कॉलेज से संदेश",
    intro: "फ़ीस अनुस्मारक, उपस्थिति चेतावनी, परिणाम और प्रमाणपत्र। साइन-इन कोड हमेशा भेजे जाते हैं।",
    notSetUp: "कॉलेज ने अभी शुरू नहीं किया",
    noAddress: "कोई नंबर या ईमेल दर्ज नहीं",
    save: "सहेजें",
    saved: "सहेजा गया।",
  },
  mr: {
    title: "कॉलेजकडून संदेश",
    intro: "शुल्क स्मरणपत्रे, उपस्थिती इशारे, निकाल आणि प्रमाणपत्रे. साइन-इन कोड नेहमी पाठवले जातात.",
    notSetUp: "कॉलेजने अद्याप सुरू केलेले नाही",
    noAddress: "नंबर किंवा ईमेल नोंदलेला नाही",
    save: "जतन करा",
    saved: "जतन केले.",
  },
};
