import type { Language } from "../lib/types";

/** The student's grievance page, in English, Hindi and Marathi. */
export interface GrievanceStrings {
  title: string;
  intro: string;
  raise: string;
  category: string;
  categories: Record<string, string>;
  sensitiveNote: string;
  subject: string;
  details: string;
  anonymous: string;
  anonymousHint: string;
  submit: string;
  mine: string;
  none: string;
  dueBy: (d: string, days: number) => string;
  statuses: Record<string, string>;
  escalated: string;
  anonymousBadge: string;
  events: Record<string, string>;
  you: string;
  college: string;
  addComment: string;
  send: string;
  resolution: string;
  feedbackAsk: string;
  yes: string;
  no: string;
  rating: string;
  comment: string;
  sendFeedback: string;
  reopenNote: string;
  yourFeedback: (stars: string) => string;
  back: string;
}

export const GRIEVANCE_STRINGS: Record<Language, GrievanceStrings> = {
  en: {
    title: "Grievances",
    intro: "Tell the college about a problem. Each grievance gets a number and a date by which it should be resolved; if it isn't, it goes to the Principal.",
    raise: "Raise a grievance",
    category: "About",
    categories: {
      academic: "Academic (teaching, syllabus)",
      examination: "Examination",
      fees: "Fees and scholarships",
      infrastructure: "Infrastructure",
      library: "Library",
      hostel: "Hostel",
      ragging: "Ragging",
      harassment: "Harassment",
      other: "Other",
    },
    sensitiveNote: "Ragging and harassment complaints go only to the Internal Complaints Committee, in confidence.",
    subject: "Subject",
    details: "What happened?",
    anonymous: "Hide my name from the staff who handle it",
    anonymousHint: "You can still follow it here and get replies.",
    submit: "Submit",
    mine: "My grievances",
    none: "You haven't raised any grievance.",
    dueBy: (d, days) => `To be resolved by ${d} (${days} working days)`,
    statuses: {
      open: "Open",
      in_progress: "Being looked into",
      resolved: "Resolved",
      closed: "Closed",
    },
    escalated: "Sent to the Principal",
    anonymousBadge: "Name hidden",
    events: {
      raised: "Raised",
      comment: "You added",
      reply: "College replied",
      taken: "Being looked into",
      resolved: "Resolved",
      feedback: "Your feedback",
      reopened: "Reopened",
      closed: "Closed",
      escalated: "Sent to the Principal",
    },
    you: "You",
    college: "College",
    addComment: "Add more details",
    send: "Send",
    resolution: "Resolution",
    feedbackAsk: "Are you satisfied with how this was resolved?",
    yes: "Yes",
    no: "No",
    rating: "Rating (1–5)",
    comment: "Comment (optional)",
    sendFeedback: "Send feedback",
    reopenNote: "If you say no, the grievance is reopened once and sent to the Principal.",
    yourFeedback: (stars) => `Your rating: ${stars}`,
    back: "All grievances",
  },
  hi: {
    title: "शिकायतें",
    intro: "किसी समस्या के बारे में कॉलेज को बताएँ। हर शिकायत को एक नंबर और समाधान की तारीख मिलती है; समय पर समाधान न होने पर वह प्राचार्य के पास जाती है।",
    raise: "शिकायत दर्ज करें",
    category: "विषय",
    categories: {
      academic: "शैक्षणिक (पढ़ाई, पाठ्यक्रम)",
      examination: "परीक्षा",
      fees: "शुल्क और छात्रवृत्ति",
      infrastructure: "बुनियादी सुविधाएँ",
      library: "पुस्तकालय",
      hostel: "हॉस्टल",
      ragging: "रैगिंग",
      harassment: "उत्पीड़न",
      other: "अन्य",
    },
    sensitiveNote: "रैगिंग और उत्पीड़न की शिकायतें गोपनीय रूप से केवल आंतरिक शिकायत समिति के पास जाती हैं।",
    subject: "शीर्षक",
    details: "क्या हुआ?",
    anonymous: "संभालने वाले कर्मचारियों से मेरा नाम छिपाएँ",
    anonymousHint: "आप फिर भी यहाँ इसे देख सकेंगे और उत्तर पा सकेंगे।",
    submit: "जमा करें",
    mine: "मेरी शिकायतें",
    none: "आपने कोई शिकायत दर्ज नहीं की है।",
    dueBy: (d, days) => `${d} तक समाधान (${days} कार्य दिवस)`,
    statuses: {
      open: "खुली",
      in_progress: "जाँच जारी",
      resolved: "समाधान हुआ",
      closed: "बंद",
    },
    escalated: "प्राचार्य को भेजी गई",
    anonymousBadge: "नाम छिपा",
    events: {
      raised: "दर्ज की",
      comment: "आपने जोड़ा",
      reply: "कॉलेज का उत्तर",
      taken: "जाँच शुरू",
      resolved: "समाधान हुआ",
      feedback: "आपकी प्रतिक्रिया",
      reopened: "फिर से खोली",
      closed: "बंद",
      escalated: "प्राचार्य को भेजी गई",
    },
    you: "आप",
    college: "कॉलेज",
    addComment: "और जानकारी जोड़ें",
    send: "भेजें",
    resolution: "समाधान",
    feedbackAsk: "क्या आप समाधान से संतुष्ट हैं?",
    yes: "हाँ",
    no: "नहीं",
    rating: "रेटिंग (1–5)",
    comment: "टिप्पणी (वैकल्पिक)",
    sendFeedback: "प्रतिक्रिया भेजें",
    reopenNote: "नहीं कहने पर शिकायत एक बार फिर खुलेगी और प्राचार्य को भेजी जाएगी।",
    yourFeedback: (stars) => `आपकी रेटिंग: ${stars}`,
    back: "सभी शिकायतें",
  },
  mr: {
    title: "तक्रारी",
    intro: "एखाद्या समस्येबद्दल कॉलेजला कळवा. प्रत्येक तक्रारीला एक क्रमांक आणि निवारणाची तारीख मिळते; वेळेत निवारण न झाल्यास ती प्राचार्यांकडे जाते.",
    raise: "तक्रार नोंदवा",
    category: "विषय",
    categories: {
      academic: "शैक्षणिक (अध्यापन, अभ्यासक्रम)",
      examination: "परीक्षा",
      fees: "शुल्क आणि शिष्यवृत्ती",
      infrastructure: "पायाभूत सुविधा",
      library: "ग्रंथालय",
      hostel: "वसतिगृह",
      ragging: "रॅगिंग",
      harassment: "छळ",
      other: "इतर",
    },
    sensitiveNote: "रॅगिंग आणि छळाच्या तक्रारी गोपनीयपणे फक्त अंतर्गत तक्रार समितीकडे जातात.",
    subject: "शीर्षक",
    details: "काय झाले?",
    anonymous: "हाताळणाऱ्या कर्मचाऱ्यांपासून माझे नाव लपवा",
    anonymousHint: "तरीही तुम्ही ती इथे पाहू शकाल आणि उत्तरे मिळवू शकाल.",
    submit: "सादर करा",
    mine: "माझ्या तक्रारी",
    none: "तुम्ही कोणतीही तक्रार नोंदवलेली नाही.",
    dueBy: (d, days) => `${d} पर्यंत निवारण (${days} कामाचे दिवस)`,
    statuses: {
      open: "खुली",
      in_progress: "तपास सुरू",
      resolved: "निवारण झाले",
      closed: "बंद",
    },
    escalated: "प्राचार्यांकडे पाठवली",
    anonymousBadge: "नाव लपवलेले",
    events: {
      raised: "नोंदवली",
      comment: "तुम्ही जोडले",
      reply: "कॉलेजचे उत्तर",
      taken: "तपास सुरू",
      resolved: "निवारण झाले",
      feedback: "तुमचा अभिप्राय",
      reopened: "पुन्हा उघडली",
      closed: "बंद",
      escalated: "प्राचार्यांकडे पाठवली",
    },
    you: "तुम्ही",
    college: "कॉलेज",
    addComment: "अधिक माहिती जोडा",
    send: "पाठवा",
    resolution: "निवारण",
    feedbackAsk: "निवारणाबद्दल तुम्ही समाधानी आहात का?",
    yes: "होय",
    no: "नाही",
    rating: "रेटिंग (1–5)",
    comment: "टिप्पणी (ऐच्छिक)",
    sendFeedback: "अभिप्राय पाठवा",
    reopenNote: "नाही म्हटल्यास तक्रार एकदा पुन्हा उघडली जाईल आणि प्राचार्यांकडे पाठवली जाईल.",
    yourFeedback: (stars) => `तुमचे रेटिंग: ${stars}`,
    back: "सर्व तक्रारी",
  },
};
