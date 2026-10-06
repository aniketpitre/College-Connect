import type { Language } from "../lib/types";

/** The public "Apply" page and the applicant's own application, in English, Hindi and Marathi. */
export interface AdmissionStrings {
  applyTitle: string;
  applyIntro: string;
  openNow: string;
  noOpen: string;
  lastDate: (d: string) => string;
  appFee: (amount: string) => string;
  seats: (n: number) => string;
  startTitle: string;
  name: string;
  mobile: string;
  email: string;
  emailHint: string;
  sendCode: string;
  sending: string;
  codeSent: string;
  code: string;
  continue: string;
  codeWrong: string;
  alreadyApplied: string;
  newApplication: string;
  enquiryTitle: string;
  enquiryIntro: string;
  programme: string;
  anyProgramme: string;
  message: string;
  sendEnquiry: string;
  enquirySent: string;
  appTitle: string;
  number: string;
  statuses: Record<string, string>;
  save: string;
  saved: string;
  choose: string;
  documentsTitle: string;
  notUploaded: string;
  upload: string;
  replace: string;
  feeTitle: string;
  feePaid: (receipt: string) => string;
  feeWaived: string;
  feeDue: (amount: string) => string;
  payOnline: string;
  payAtOffice: string;
  submit: string;
  submitTitle: string;
  submitIntro: string;
  stillNeeded: string;
  missing: Record<string, string>;
  returned: (reason: string) => string;
  rejected: (reason: string) => string;
  waiting: (rank: number) => string;
  offer: (seat: string, date: string) => string;
  admitted: (prn: string) => string;
  lapsed: string;
  closed: string;
}

const MISSING_EN = {
  name: "your name",
  dob: "date of birth",
  gender: "gender",
  phone: "mobile number",
  email: "email",
  category_id: "category",
  programme_id: "programme",
  previous_education: "previous exam percentage",
  fee: "application fee",
};

export const ADMISSION_STRINGS: Record<Language, AdmissionStrings> = {
  en: {
    applyTitle: "Apply for admission",
    applyIntro: "Fill in the form online, upload your marksheets and pay the application fee. You can come back and finish it any time before the last date.",
    openNow: "Admissions open now",
    noOpen: "No admissions are open right now. Leave your number below and the college will call you.",
    lastDate: (d) => `Last date: ${d}`,
    appFee: (a) => `Application fee ${a}`,
    seats: (n) => `${n} seats`,
    startTitle: "Start your application",
    name: "Full name (as on the marksheet)",
    mobile: "Mobile number",
    email: "Email",
    emailHint: "Sign-in codes and updates come here.",
    sendCode: "Send sign-in code",
    sending: "Sending…",
    codeSent: "A 6-digit code has been sent to your email. It works for 10 minutes.",
    code: "Sign-in code",
    continue: "Continue",
    codeWrong: "That code is wrong or has expired. Ask for a new one.",
    alreadyApplied: "Already started? Sign in with your mobile number",
    newApplication: "Start a new application instead",
    enquiryTitle: "Have a question?",
    enquiryIntro: "Leave your number and the admission office will call you.",
    programme: "Programme",
    anyProgramme: "Not sure yet",
    message: "Your question (optional)",
    sendEnquiry: "Call me back",
    enquirySent: "Thank you. The admission office will call you soon.",
    appTitle: "My application",
    number: "Application no.",
    statuses: {
      draft: "Not submitted yet",
      submitted: "Submitted: the college is checking it",
      returned: "Returned: please correct and submit again",
      verified: "Verified: waiting for the merit list",
      rejected: "Not accepted",
      offered: "Admission offered",
      waiting: "On the waiting list",
      lapsed: "Offer lapsed",
      admitted: "Admitted",
      cancelled: "Admission cancelled",
    },
    save: "Save",
    saved: "Saved.",
    choose: "Choose…",
    documentsTitle: "Documents",
    notUploaded: "Not uploaded yet",
    upload: "Upload",
    replace: "Replace",
    feeTitle: "Application fee",
    feePaid: (r) => `Paid. Receipt ${r}.`,
    feeWaived: "Not charged.",
    feeDue: (a) => `${a} to pay.`,
    payOnline: "Pay online",
    payAtOffice: "Pay at the college office; they will mark it paid.",
    submit: "Submit application",
    submitTitle: "Submit",
    submitIntro: "Check everything first: after you submit, the college checks it and you can't change it unless they return it.",
    stillNeeded: "Still needed:",
    missing: MISSING_EN,
    returned: (r) => `The college returned your application: ${r}`,
    rejected: (r) => `Your application was not accepted: ${r}`,
    waiting: (n) => `You are number ${n} on the merit list. If a seat becomes free in the next round, you will be told.`,
    offer: (seat, d) => `You are offered a seat (${seat}). Come to the college office with your original documents and the fees by ${d} to confirm.`,
    admitted: (p) => `Your admission is confirmed. Your PRN is ${p}. Sign in as a student with the PRN and the temporary password on your admission slip.`,
    lapsed: "Your offer lapsed because the admission wasn't confirmed by the last date. Contact the admission office.",
    closed: "The last date has passed.",
  },
  hi: {
    applyTitle: "प्रवेश के लिए आवेदन",
    applyIntro: "फ़ॉर्म ऑनलाइन भरें, अंकपत्र अपलोड करें और आवेदन शुल्क दें। अंतिम तिथि से पहले कभी भी लौटकर इसे पूरा कर सकते हैं।",
    openNow: "अभी खुले प्रवेश",
    noOpen: "अभी कोई प्रवेश खुला नहीं है। नीचे अपना नंबर दें, कॉलेज आपको कॉल करेगा।",
    lastDate: (d) => `अंतिम तिथि: ${d}`,
    appFee: (a) => `आवेदन शुल्क ${a}`,
    seats: (n) => `${n} सीटें`,
    startTitle: "आवेदन शुरू करें",
    name: "पूरा नाम (अंकपत्र के अनुसार)",
    mobile: "मोबाइल नंबर",
    email: "ईमेल",
    emailHint: "साइन-इन कोड और सूचनाएँ यहाँ आएँगी।",
    sendCode: "साइन-इन कोड भेजें",
    sending: "भेजा जा रहा है…",
    codeSent: "आपके ईमेल पर 6 अंकों का कोड भेजा गया है। यह 10 मिनट तक चलेगा।",
    code: "साइन-इन कोड",
    continue: "आगे बढ़ें",
    codeWrong: "कोड गलत है या उसकी समय-सीमा समाप्त हो गई है। नया कोड मंगाएँ।",
    alreadyApplied: "पहले से शुरू किया है? मोबाइल नंबर से साइन इन करें",
    newApplication: "नया आवेदन शुरू करें",
    enquiryTitle: "कोई प्रश्न है?",
    enquiryIntro: "अपना नंबर दें, प्रवेश कार्यालय आपको कॉल करेगा।",
    programme: "पाठ्यक्रम",
    anyProgramme: "अभी तय नहीं",
    message: "आपका प्रश्न (वैकल्पिक)",
    sendEnquiry: "मुझे कॉल करें",
    enquirySent: "धन्यवाद। प्रवेश कार्यालय जल्द ही आपको कॉल करेगा।",
    appTitle: "मेरा आवेदन",
    number: "आवेदन क्र.",
    statuses: {
      draft: "अभी जमा नहीं किया",
      submitted: "जमा किया: कॉलेज जाँच रहा है",
      returned: "लौटाया गया: सुधार कर फिर से जमा करें",
      verified: "सत्यापित: मेरिट सूची की प्रतीक्षा",
      rejected: "स्वीकार नहीं हुआ",
      offered: "प्रवेश का प्रस्ताव",
      waiting: "प्रतीक्षा सूची में",
      lapsed: "प्रस्ताव समाप्त",
      admitted: "प्रवेश मिला",
      cancelled: "प्रवेश रद्द",
    },
    save: "सहेजें",
    saved: "सहेजा गया।",
    choose: "चुनें…",
    documentsTitle: "दस्तावेज़",
    notUploaded: "अभी अपलोड नहीं",
    upload: "अपलोड करें",
    replace: "बदलें",
    feeTitle: "आवेदन शुल्क",
    feePaid: (r) => `भुगतान हो गया। रसीद ${r}।`,
    feeWaived: "शुल्क नहीं लिया गया।",
    feeDue: (a) => `${a} देना है।`,
    payOnline: "ऑनलाइन भुगतान करें",
    payAtOffice: "कॉलेज कार्यालय में भुगतान करें; वे इसे दर्ज कर देंगे।",
    submit: "आवेदन जमा करें",
    submitTitle: "जमा करें",
    submitIntro: "पहले सब जाँच लें: जमा करने के बाद कॉलेज इसे जाँचता है और लौटाए बिना आप इसे बदल नहीं सकते।",
    stillNeeded: "अभी चाहिए:",
    missing: {
      name: "आपका नाम",
      dob: "जन्म तिथि",
      gender: "लिंग",
      phone: "मोबाइल नंबर",
      email: "ईमेल",
      category_id: "श्रेणी",
      programme_id: "पाठ्यक्रम",
      previous_education: "पिछली परीक्षा का प्रतिशत",
      fee: "आवेदन शुल्क",
    },
    returned: (r) => `कॉलेज ने आपका आवेदन लौटाया: ${r}`,
    rejected: (r) => `आपका आवेदन स्वीकार नहीं हुआ: ${r}`,
    waiting: (n) => `मेरिट सूची में आपका क्रमांक ${n} है। अगले चरण में सीट खाली होने पर आपको बताया जाएगा।`,
    offer: (seat, d) => `आपको सीट (${seat}) का प्रस्ताव है। पुष्टि के लिए ${d} तक मूल दस्तावेज़ और फ़ीस लेकर कॉलेज कार्यालय आएँ।`,
    admitted: (p) => `आपका प्रवेश पक्का हो गया है। आपका PRN ${p} है। प्रवेश पर्ची पर दिए अस्थायी पासवर्ड और PRN से छात्र के रूप में साइन इन करें।`,
    lapsed: "अंतिम तिथि तक पुष्टि न होने से आपका प्रस्ताव समाप्त हो गया। प्रवेश कार्यालय से संपर्क करें।",
    closed: "अंतिम तिथि बीत चुकी है।",
  },
  mr: {
    applyTitle: "प्रवेशासाठी अर्ज",
    applyIntro: "फॉर्म ऑनलाइन भरा, गुणपत्रिका अपलोड करा आणि अर्ज शुल्क भरा. शेवटच्या तारखेपूर्वी कधीही परत येऊन पूर्ण करू शकता.",
    openNow: "आता सुरू असलेले प्रवेश",
    noOpen: "सध्या कोणतेही प्रवेश सुरू नाहीत. खाली तुमचा नंबर द्या, कॉलेज तुम्हाला फोन करेल.",
    lastDate: (d) => `शेवटची तारीख: ${d}`,
    appFee: (a) => `अर्ज शुल्क ${a}`,
    seats: (n) => `${n} जागा`,
    startTitle: "अर्ज सुरू करा",
    name: "पूर्ण नाव (गुणपत्रिकेप्रमाणे)",
    mobile: "मोबाइल नंबर",
    email: "ईमेल",
    emailHint: "साइन-इन कोड आणि सूचना इथे येतील.",
    sendCode: "साइन-इन कोड पाठवा",
    sending: "पाठवत आहे…",
    codeSent: "तुमच्या ईमेलवर 6 अंकी कोड पाठवला आहे. तो 10 मिनिटे चालेल.",
    code: "साइन-इन कोड",
    continue: "पुढे जा",
    codeWrong: "कोड चुकीचा आहे किंवा त्याची मुदत संपली आहे. नवीन कोड मागवा.",
    alreadyApplied: "आधीच सुरू केला आहे? मोबाइल नंबरने साइन इन करा",
    newApplication: "नवीन अर्ज सुरू करा",
    enquiryTitle: "काही प्रश्न आहे?",
    enquiryIntro: "तुमचा नंबर द्या, प्रवेश कार्यालय तुम्हाला फोन करेल.",
    programme: "अभ्यासक्रम",
    anyProgramme: "अजून ठरले नाही",
    message: "तुमचा प्रश्न (ऐच्छिक)",
    sendEnquiry: "मला फोन करा",
    enquirySent: "धन्यवाद. प्रवेश कार्यालय लवकरच तुम्हाला फोन करेल.",
    appTitle: "माझा अर्ज",
    number: "अर्ज क्र.",
    statuses: {
      draft: "अजून सादर केला नाही",
      submitted: "सादर केला: कॉलेज तपासत आहे",
      returned: "परत केला: दुरुस्त करून पुन्हा सादर करा",
      verified: "पडताळला: गुणवत्ता यादीची प्रतीक्षा",
      rejected: "स्वीकारला नाही",
      offered: "प्रवेशाची ऑफर",
      waiting: "प्रतीक्षा यादीत",
      lapsed: "ऑफर संपली",
      admitted: "प्रवेश निश्चित",
      cancelled: "प्रवेश रद्द",
    },
    save: "जतन करा",
    saved: "जतन केले.",
    choose: "निवडा…",
    documentsTitle: "कागदपत्रे",
    notUploaded: "अजून अपलोड केले नाही",
    upload: "अपलोड करा",
    replace: "बदला",
    feeTitle: "अर्ज शुल्क",
    feePaid: (r) => `भरले. पावती ${r}.`,
    feeWaived: "शुल्क आकारले नाही.",
    feeDue: (a) => `${a} भरायचे आहेत.`,
    payOnline: "ऑनलाइन भरा",
    payAtOffice: "कॉलेज कार्यालयात भरा; ते नोंद करतील.",
    submit: "अर्ज सादर करा",
    submitTitle: "सादर करा",
    submitIntro: "आधी सर्व तपासा: सादर केल्यानंतर कॉलेज तपासते आणि परत केल्याशिवाय तुम्ही बदल करू शकत नाही.",
    stillNeeded: "अजून हवे:",
    missing: {
      name: "तुमचे नाव",
      dob: "जन्मतारीख",
      gender: "लिंग",
      phone: "मोबाइल नंबर",
      email: "ईमेल",
      category_id: "प्रवर्ग",
      programme_id: "अभ्यासक्रम",
      previous_education: "मागील परीक्षेची टक्केवारी",
      fee: "अर्ज शुल्क",
    },
    returned: (r) => `कॉलेजने तुमचा अर्ज परत केला: ${r}`,
    rejected: (r) => `तुमचा अर्ज स्वीकारला नाही: ${r}`,
    waiting: (n) => `गुणवत्ता यादीत तुमचा क्रमांक ${n} आहे. पुढील फेरीत जागा रिकामी झाल्यास कळवले जाईल.`,
    offer: (seat, d) => `तुम्हाला जागा (${seat}) देऊ केली आहे. निश्चितीसाठी ${d} पर्यंत मूळ कागदपत्रे आणि शुल्क घेऊन कॉलेज कार्यालयात या.`,
    admitted: (p) => `तुमचा प्रवेश निश्चित झाला. तुमचा PRN ${p} आहे. प्रवेश पावतीवरील तात्पुरता पासवर्ड आणि PRN ने विद्यार्थी म्हणून साइन इन करा.`,
    lapsed: "शेवटच्या तारखेपर्यंत निश्चिती न झाल्याने तुमची ऑफर संपली. प्रवेश कार्यालयाशी संपर्क साधा.",
    closed: "शेवटची तारीख उलटून गेली आहे.",
  },
};
