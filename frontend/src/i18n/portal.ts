import type { Language } from "../lib/types";

/** Student portal: home and My fees. */
export interface PortalStrings {
  greeting: string;
  needsAttention: string;
  allClear: string;
  balanceDue: string;
  inCredit: string;
  academicYear: string;
  askTitle: string;
  askBody: string;
  askButton: string;
  quickLinks: string;
  feeOverdue: (amount: string, since: string) => string;
  feeDueSoon: (amount: string, label: string, date: string) => string;
  documentRejected: (doc: string) => string;
  correctionApproved: string;
  correctionRejected: string;
  payAtOffice: string;
  view: string;
  newNotice: string;
  attendanceLow: (code: string, pct: number, n: number) => string;
  attendanceWarning: (code: string, pct: number, n: number) => string;
  attendanceTile: string;
  examForm: (exam: string, date: string) => string;
  hallTicket: (exam: string) => string;
  results: (exam: string) => string;
  certificateReady: (kind: string) => string;
  // My fees
  feesTitle: string;
  payOnline: string;
  payTitle: string;
  payAmount: string;
  payHint: string;
  payNow: string;
  paying: string;
  paySuccess: (receipt: string) => string;
  payPending: string;
  cancel: string;
  year: string;
  totalFee: string;
  paid: string;
  concessionsScholarships: string;
  installments: string;
  due: string;
  paidLabel: string;
  overdue: string;
  dueBy: (date: string) => string;
  receipts: string;
  noReceipts: string;
  download: string;
  cancelled: string;
  statement: string;
  statementPdf: string;
  date: string;
  entry: string;
  charged: string;
  credited: string;
  balance: string;
  noFees: string;
  entryLabels: Record<string, string>;
}

const EN: PortalStrings = {
  greeting: "Hello",
  needsAttention: "Needs your attention",
  allClear: "Nothing needs your attention right now.",
  balanceDue: "Fees due",
  inCredit: "In credit",
  academicYear: "Academic year",
  askTitle: "Ask CollegeConnect",
  askBody: "Questions about rules, exams, scholarships or admissions? Get an answer with the official source.",
  askButton: "Ask a question",
  quickLinks: "Go to",
  feeOverdue: (amount, since) => `${amount} of your fees is overdue (since ${since}).`,
  feeDueSoon: (amount, label, date) => `${label}: ${amount} is due by ${date}.`,
  documentRejected: (doc) => `Your ${doc} was not accepted. Upload a clearer copy.`,
  correctionApproved: "The office corrected your details as you asked.",
  correctionRejected: "The office did not change your details.",
  payAtOffice: "Pay at the college accounts counter.",
  view: "View",
  newNotice: "New notice",
  attendanceLow: (code, pct, n) => `Attendance in ${code} is ${pct}%. Attend the next ${n} lectures to reach the minimum.`,
  attendanceWarning: (code, pct, n) => `Attendance in ${code} is ${pct}%. You can miss only ${n} more.`,
  attendanceTile: "Attendance",
  examForm: (exam, date) => `Fill in your exam form for ${exam} by ${date}.`,
  hallTicket: (exam) => `Your hall ticket for ${exam} is ready to download.`,
  results: (exam) => `Results for ${exam} are out.`,
  certificateReady: (kind) => `Your ${kind} is ready. Download it or collect it from the office.`,
  feesTitle: "My fees",
  payOnline: "Pay online",
  payTitle: "Pay fees online",
  payAmount: "Amount",
  payHint: "UPI, debit or credit card, or net banking. The receipt appears here as soon as the payment goes through.",
  payNow: "Continue to payment",
  paying: "Opening the payment page…",
  paySuccess: (r) => `Payment received. Receipt ${r} is ready to download.`,
  payPending: "We are confirming your payment with the bank. Your receipt will appear here shortly; you don't need to pay again.",
  cancel: "Cancel",
  year: "Year",
  totalFee: "Total fee",
  paid: "Paid",
  concessionsScholarships: "Concessions & scholarships",
  installments: "Installments",
  due: "due",
  paidLabel: "Paid",
  overdue: "overdue",
  dueBy: (date) => `due by ${date}`,
  receipts: "Receipts",
  noReceipts: "No payments yet.",
  download: "Download",
  cancelled: "Cancelled",
  statement: "Statement",
  statementPdf: "Download fee statement (PDF)",
  date: "Date",
  entry: "Entry",
  charged: "Charged",
  credited: "Credited",
  balance: "Balance",
  noFees: "Your fees for this year haven't been added yet.",
  entryLabels: {
    demand: "Fee for the year",
    charge: "Charge",
    opening_due: "Previous dues",
    refund: "Refund paid",
    payment: "Payment",
    concession: "Concession",
    scholarship: "Scholarship",
    opening_paid: "Paid before CollegeConnect",
    reversal: "Reversal",
  },
};

const HI: PortalStrings = {
  greeting: "नमस्ते",
  needsAttention: "आपके ध्यान के लिए",
  allClear: "अभी आपके लिए कुछ बाकी नहीं है।",
  balanceDue: "बकाया फ़ीस",
  inCredit: "आपके खाते में जमा",
  academicYear: "शैक्षणिक वर्ष",
  askTitle: "कॉलेजकनेक्ट से पूछें",
  askBody: "नियम, परीक्षा, छात्रवृत्ति या प्रवेश के बारे में प्रश्न? आधिकारिक स्रोत के साथ उत्तर पाएं।",
  askButton: "प्रश्न पूछें",
  quickLinks: "जाएं",
  feeOverdue: (amount, since) => `आपकी ${amount} फ़ीस बकाया है (${since} से)।`,
  feeDueSoon: (amount, label, date) => `${label}: ${amount} ${date} तक भरनी है।`,
  documentRejected: (doc) => `आपका ${doc} स्वीकार नहीं हुआ। साफ़ प्रति अपलोड करें।`,
  correctionApproved: "कार्यालय ने आपके अनुरोध के अनुसार जानकारी सुधार दी।",
  correctionRejected: "कार्यालय ने आपकी जानकारी नहीं बदली।",
  payAtOffice: "कॉलेज के लेखा काउंटर पर भुगतान करें।",
  view: "देखें",
  newNotice: "नई सूचना",
  attendanceLow: (code, pct, n) => `${code} में उपस्थिति ${pct}% है। न्यूनतम तक पहुँचने के लिए अगले ${n} लेक्चर में आएँ।`,
  attendanceWarning: (code, pct, n) => `${code} में उपस्थिति ${pct}% है। आप केवल ${n} और छोड़ सकते हैं।`,
  attendanceTile: "उपस्थिति",
  examForm: (exam, date) => `${exam} का परीक्षा फ़ॉर्म ${date} तक भरें।`,
  hallTicket: (exam) => `${exam} का हॉल टिकट डाउनलोड के लिए तैयार है।`,
  results: (exam) => `${exam} का परिणाम आ गया है।`,
  certificateReady: (kind) => `आपका ${kind} तैयार है। डाउनलोड करें या कार्यालय से लें।`,
  feesTitle: "मेरी फ़ीस",
  payOnline: "ऑनलाइन भुगतान करें",
  payTitle: "फ़ीस का ऑनलाइन भुगतान",
  payAmount: "राशि",
  payHint: "UPI, डेबिट या क्रेडिट कार्ड, या नेट बैंकिंग। भुगतान होते ही रसीद यहाँ दिखेगी।",
  payNow: "भुगतान पर जाएँ",
  paying: "भुगतान पेज खुल रहा है…",
  paySuccess: (r) => `भुगतान प्राप्त हुआ। रसीद ${r} डाउनलोड के लिए तैयार है।`,
  payPending: "हम बैंक से आपके भुगतान की पुष्टि कर रहे हैं। रसीद जल्द ही यहाँ दिखेगी; दोबारा भुगतान न करें।",
  cancel: "रद्द करें",
  year: "वर्ष",
  totalFee: "कुल फ़ीस",
  paid: "भुगतान किया",
  concessionsScholarships: "छूट और छात्रवृत्ति",
  installments: "किस्तें",
  due: "बकाया",
  paidLabel: "भुगतान हो गया",
  overdue: "देय तिथि निकल गई",
  dueBy: (date) => `${date} तक`,
  receipts: "रसीदें",
  noReceipts: "अभी कोई भुगतान नहीं।",
  download: "डाउनलोड",
  cancelled: "रद्द",
  statement: "विवरण",
  statementPdf: "फ़ीस विवरण डाउनलोड करें (PDF)",
  date: "दिनांक",
  entry: "विवरण",
  charged: "लगाया गया",
  credited: "जमा",
  balance: "शेष",
  noFees: "इस वर्ष की आपकी फ़ीस अभी जोड़ी नहीं गई है।",
  entryLabels: {
    demand: "वर्ष की फ़ीस",
    charge: "शुल्क",
    opening_due: "पिछला बकाया",
    refund: "धनवापसी",
    payment: "भुगतान",
    concession: "छूट",
    scholarship: "छात्रवृत्ति",
    opening_paid: "कॉलेजकनेक्ट से पहले भुगतान",
    reversal: "रद्दीकरण",
  },
};

const MR: PortalStrings = {
  greeting: "नमस्कार",
  needsAttention: "तुमच्या लक्षासाठी",
  allClear: "सध्या तुमच्यासाठी काहीही बाकी नाही.",
  balanceDue: "थकीत शुल्क",
  inCredit: "तुमच्या खात्यात जमा",
  academicYear: "शैक्षणिक वर्ष",
  askTitle: "कॉलेजकनेक्टला विचारा",
  askBody: "नियम, परीक्षा, शिष्यवृत्ती किंवा प्रवेशाबद्दल प्रश्न? अधिकृत स्रोतासह उत्तर मिळवा.",
  askButton: "प्रश्न विचारा",
  quickLinks: "येथे जा",
  feeOverdue: (amount, since) => `तुमचे ${amount} शुल्क थकले आहे (${since} पासून).`,
  feeDueSoon: (amount, label, date) => `${label}: ${amount} ${date} पर्यंत भरायचे आहे.`,
  documentRejected: (doc) => `तुमचे ${doc} स्वीकारले नाही. स्पष्ट प्रत अपलोड करा.`,
  correctionApproved: "कार्यालयाने तुमच्या विनंतीनुसार माहिती दुरुस्त केली.",
  correctionRejected: "कार्यालयाने तुमची माहिती बदलली नाही.",
  payAtOffice: "महाविद्यालयाच्या लेखा खिडकीवर भरणा करा.",
  view: "पहा",
  newNotice: "नवीन सूचना",
  attendanceLow: (code, pct, n) => `${code} मध्ये हजेरी ${pct}% आहे. किमान गाठण्यासाठी पुढील ${n} लेक्चर उपस्थित राहा.`,
  attendanceWarning: (code, pct, n) => `${code} मध्ये हजेरी ${pct}% आहे. तुम्ही फक्त आणखी ${n} चुकवू शकता.`,
  attendanceTile: "हजेरी",
  examForm: (exam, date) => `${exam} चा परीक्षा अर्ज ${date} पर्यंत भरा.`,
  hallTicket: (exam) => `${exam} चे हॉल तिकीट डाउनलोडसाठी तयार आहे.`,
  results: (exam) => `${exam} चा निकाल लागला आहे.`,
  certificateReady: (kind) => `तुमचे ${kind} तयार आहे. डाउनलोड करा किंवा कार्यालयातून घ्या.`,
  feesTitle: "माझे शुल्क",
  payOnline: "ऑनलाइन भरा",
  payTitle: "शुल्क ऑनलाइन भरा",
  payAmount: "रक्कम",
  payHint: "UPI, डेबिट किंवा क्रेडिट कार्ड, किंवा नेट बँकिंग. पैसे भरताच पावती इथे दिसेल.",
  payNow: "पैसे भरण्यासाठी पुढे जा",
  paying: "पेमेंट पेज उघडत आहे…",
  paySuccess: (r) => `पैसे मिळाले. पावती ${r} डाउनलोडसाठी तयार आहे.`,
  payPending: "आम्ही बँकेकडून तुमच्या पेमेंटची खात्री करत आहोत. पावती लवकरच इथे दिसेल; पुन्हा पैसे भरू नका.",
  cancel: "रद्द करा",
  year: "वर्ष",
  totalFee: "एकूण शुल्क",
  paid: "भरले",
  concessionsScholarships: "सवलत व शिष्यवृत्ती",
  installments: "हप्ते",
  due: "बाकी",
  paidLabel: "भरले",
  overdue: "मुदत संपली",
  dueBy: (date) => `${date} पर्यंत`,
  receipts: "पावत्या",
  noReceipts: "अजून कोणताही भरणा नाही.",
  download: "डाउनलोड",
  cancelled: "रद्द",
  statement: "विवरण",
  statementPdf: "शुल्क विवरण डाउनलोड करा (PDF)",
  date: "दिनांक",
  entry: "तपशील",
  charged: "आकारले",
  credited: "जमा",
  balance: "शिल्लक",
  noFees: "या वर्षीचे तुमचे शुल्क अजून जोडलेले नाही.",
  entryLabels: {
    demand: "वर्षाचे शुल्क",
    charge: "शुल्क",
    opening_due: "मागील थकबाकी",
    refund: "परतावा",
    payment: "भरणा",
    concession: "सवलत",
    scholarship: "शिष्यवृत्ती",
    opening_paid: "कॉलेजकनेक्टपूर्वी भरलेले",
    reversal: "रद्द नोंद",
  },
};

export const PORTAL_STRINGS: Record<Language, PortalStrings> = { en: EN, hi: HI, mr: MR };
