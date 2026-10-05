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
  },
};
