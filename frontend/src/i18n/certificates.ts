import type { Language } from "../lib/types";

/** Certificate strings students see. */
export interface CertStrings {
  title: string;
  ask: string;
  kind: string;
  purpose: string;
  purposeHint: string;
  reasonForLeaving: string;
  organisation: string;
  from: string;
  to: string;
  submit: string;
  readyIn: (days: number) => string;
  promised: (date: string) => string;
  overdue: string;
  status: Record<string, string>;
  download: string;
  none: string;
  sent: string;
  readOnly: string;
  types: Record<string, string>;
}

export const CERT_STRINGS: Record<Language, CertStrings> = {
  en: {
    title: "My certificates",
    ask: "Ask for a certificate",
    kind: "Certificate",
    purpose: "What is it for?",
    purposeHint: "e.g. bank loan, passport, scholarship",
    reasonForLeaving: "Reason for leaving",
    organisation: "Organisation",
    from: "From",
    to: "To",
    submit: "Send request",
    readyIn: (d) => `Usually ready in ${d} working day${d > 1 ? "s" : ""}.`,
    promised: (d) => `Promised by ${d}`,
    overdue: "Late: the Principal has been told.",
    status: { requested: "Requested", verified: "Checked by the office", signed: "Signed", ready: "Ready", rejected: "Not issued" },
    download: "Download (PDF)",
    none: "No requests yet.",
    sent: "Request sent. You can follow it here.",
    readOnly: "You have left the college: your account is read-only. You can still download your certificates and receipts.",
    types: {
      bonafide: "Bonafide certificate",
      character: "Character certificate",
      fee_paid: "Fee-paid letter",
      tc: "Transfer certificate (TC)",
      migration: "Migration certificate",
      noc: "No-objection certificate (internship)",
    },
  },
  hi: {
    title: "मेरे प्रमाणपत्र",
    ask: "प्रमाणपत्र के लिए आवेदन करें",
    kind: "प्रमाणपत्र",
    purpose: "किस लिए?",
    purposeHint: "जैसे बैंक लोन, पासपोर्ट, छात्रवृत्ति",
    reasonForLeaving: "कॉलेज छोड़ने का कारण",
    organisation: "संस्था",
    from: "से",
    to: "तक",
    submit: "आवेदन भेजें",
    readyIn: (d) => `आमतौर पर ${d} कार्य दिवस में तैयार।`,
    promised: (d) => `${d} तक देने का वादा`,
    overdue: "देरी: प्राचार्य को सूचित किया गया है।",
    status: { requested: "आवेदन किया", verified: "कार्यालय ने जांचा", signed: "हस्ताक्षरित", ready: "तैयार", rejected: "जारी नहीं" },
    download: "डाउनलोड करें (PDF)",
    none: "अभी कोई आवेदन नहीं।",
    sent: "आवेदन भेज दिया गया। आप इसे यहाँ देख सकते हैं।",
    readOnly: "आपने कॉलेज छोड़ दिया है: आपका खाता केवल देखने के लिए है। आप अपने प्रमाणपत्र और रसीदें डाउनलोड कर सकते हैं।",
    types: {
      bonafide: "बोनाफाइड प्रमाणपत्र",
      character: "चरित्र प्रमाणपत्र",
      fee_paid: "शुल्क भुगतान पत्र",
      tc: "स्थानांतरण प्रमाणपत्र (TC)",
      migration: "माइग्रेशन प्रमाणपत्र",
      noc: "अनापत्ति प्रमाणपत्र (इंटर्नशिप)",
    },
  },
  mr: {
    title: "माझी प्रमाणपत्रे",
    ask: "प्रमाणपत्रासाठी अर्ज करा",
    kind: "प्रमाणपत्र",
    purpose: "कशासाठी?",
    purposeHint: "उदा. बँक कर्ज, पासपोर्ट, शिष्यवृत्ती",
    reasonForLeaving: "कॉलेज सोडण्याचे कारण",
    organisation: "संस्था",
    from: "पासून",
    to: "पर्यंत",
    submit: "अर्ज पाठवा",
    readyIn: (d) => `साधारणपणे ${d} कामकाजाच्या दिवसांत तयार.`,
    promised: (d) => `${d} पर्यंत देण्याचे आश्वासन`,
    overdue: "उशीर: प्राचार्यांना कळवले आहे.",
    status: { requested: "अर्ज केला", verified: "कार्यालयाने तपासले", signed: "स्वाक्षरी झाली", ready: "तयार", rejected: "दिले नाही" },
    download: "डाउनलोड करा (PDF)",
    none: "अजून कोणताही अर्ज नाही.",
    sent: "अर्ज पाठवला. तुम्ही तो इथे पाहू शकता.",
    readOnly: "तुम्ही कॉलेज सोडले आहे: तुमचे खाते फक्त पाहण्यासाठी आहे. तुम्ही तुमची प्रमाणपत्रे आणि पावत्या डाउनलोड करू शकता.",
    types: {
      bonafide: "बोनाफाईड प्रमाणपत्र",
      character: "चारित्र्य प्रमाणपत्र",
      fee_paid: "शुल्क भरल्याचे पत्र",
      tc: "शाळा/कॉलेज सोडल्याचा दाखला (TC)",
      migration: "स्थलांतर प्रमाणपत्र",
      noc: "ना-हरकत प्रमाणपत्र (इंटर्नशिप)",
    },
  },
};
