import type { Language } from "../lib/types";

export type PortalKey = "student" | "staff" | "parent";

export interface HomeStrings {
  nav: { about: string; academics: string; campus: string; admissions: string };
  login: string;
  goToPortal: string;
  collegeFallback: string;
  heroEyebrow: string;
  heroWords: string[];
  heroText: string;
  apply: string;
  explore: string;
  stats: { programmes: string; departments: string; languages: string; online: string };
  aboutEyebrow: string;
  aboutTitle: string;
  aboutText: string;
  pillars: { title: string; text: string }[];
  academicsEyebrow: string;
  academicsTitle: string;
  academicsText: string;
  years: (n: number) => string;
  noProgrammes: string;
  campusEyebrow: string;
  campusTitle: string;
  campusItems: { key: "library" | "hostel" | "placement" | "exams" | "scholarship" | "care"; title: string; text: string }[];
  admissionsTitle: string;
  admissionsText: string;
  admissionsSteps: string[];
  portalsEyebrow: string;
  portalsTitle: string;
  portals: { key: PortalKey; title: string; text: string; action: string }[];
  aiTitle: string;
  aiText: string;
  aiAction: string;
  aiOpen: string;
  verify: string;
  affiliated: string;
  footer: string;
}

/** The public home page (students, parents and applicants read it in their language). */
export const HOME_STRINGS: Record<Language, HomeStrings> = {
  en: {
    nav: { about: "About", academics: "Academics", campus: "Campus life", admissions: "Admissions" },
    login: "Login",
    goToPortal: "Go to my portal",
    collegeFallback: "Our College",
    heroEyebrow: "Welcome to",
    heroWords: ["Learn.", "Grow.", "Belong."],
    heroText: "A place to study, discover and build your future, with teachers who know you by name and a campus that runs online.",
    apply: "Apply for admission",
    explore: "Explore the college",
    stats: { programmes: "Programmes", departments: "Departments", languages: "Languages", online: "Online services" },
    aboutEyebrow: "About the college",
    aboutTitle: "Education with a personal touch",
    aboutText:
      "Every student has a mentor, every class has its timetable and attendance online, and every result, receipt and certificate is a click away for students and parents.",
    pillars: [
      { title: "Teaching that cares", text: "Mentors keep an eye on attendance and marks and step in early when someone needs help." },
      { title: "Exams on time", text: "Exam forms, hall tickets and results online, with the university's rules built in." },
      { title: "Transparent fees", text: "Pay online, get a receipt at once, and see every rupee in your statement." },
      { title: "Certificates without queues", text: "Request bonafide and other certificates online, each with a QR code anyone can check." },
    ],
    academicsEyebrow: "Academics",
    academicsTitle: "Programmes we offer",
    academicsText: "Undergraduate programmes affiliated to the university, taught by experienced faculty.",
    years: (n) => `${n} ${n === 1 ? "year" : "years"}`,
    noProgrammes: "Programmes will be listed here soon.",
    campusEyebrow: "Campus life",
    campusTitle: "More than a classroom",
    campusItems: [
      { key: "library", title: "Library", text: "Thousands of books, reservations online and reminders before the due date." },
      { key: "hostel", title: "Hostel", text: "Safe rooms, a weekly mess menu, out-passes with parents told at once." },
      { key: "placement", title: "Placements", text: "Campus drives, eligibility checked for you and offers tracked in one place." },
      { key: "exams", title: "Exams & results", text: "Hall tickets, results, SGPA and CGPA, and revaluation requests online." },
      { key: "scholarship", title: "Scholarships", text: "See which scholarships you can apply for, and never miss a deadline." },
      { key: "care", title: "Student care", text: "Raise a grievance, anonymously if you like, and get an answer on time." },
    ],
    admissionsTitle: "Admissions are online",
    admissionsText: "Apply from your phone in a few minutes. No forms to print, no queues.",
    admissionsSteps: ["Sign in with your mobile number", "Fill the form and upload documents", "Pay the fee and track your application"],
    portalsEyebrow: "Portals",
    portalsTitle: "One login for the whole college",
    portals: [
      { key: "student", title: "Students", text: "Fees, attendance, marks, results, certificates and notices.", action: "Student login" },
      { key: "staff", title: "Staff", text: "Office, accounts, teaching, exams, library, hostel and placement.", action: "Staff login" },
      { key: "parent", title: "Parents", text: "Your child's fees, attendance and results, with a code on your mobile.", action: "Parent login" },
    ],
    aiTitle: "Ask CollegeConnect AI",
    aiText: "Want more information? Ask about fees, exams, admissions or any notice, in English, हिंदी or मराठी. Log in to start.",
    aiAction: "Log in to ask",
    aiOpen: "Open my portal to ask",
    verify: "Got a certificate or receipt from us? Scan its QR code to check it is genuine.",
    affiliated: "Affiliated to",
    footer: "Your data is visible only to you and the staff who need it.",
  },
  hi: {
    nav: { about: "परिचय", academics: "शिक्षा", campus: "कैंपस जीवन", admissions: "प्रवेश" },
    login: "लॉगिन",
    goToPortal: "मेरे पोर्टल पर जाएं",
    collegeFallback: "हमारा कॉलेज",
    heroEyebrow: "स्वागत है",
    heroWords: ["सीखें।", "बढ़ें।", "जुड़ें।"],
    heroText: "पढ़ने, खोजने और अपना भविष्य बनाने की जगह — ऐसे शिक्षक जो आपको नाम से जानते हैं, और एक कैंपस जो ऑनलाइन चलता है।",
    apply: "प्रवेश के लिए आवेदन",
    explore: "कॉलेज देखें",
    stats: { programmes: "पाठ्यक्रम", departments: "विभाग", languages: "भाषाएं", online: "ऑनलाइन सेवाएं" },
    aboutEyebrow: "कॉलेज के बारे में",
    aboutTitle: "व्यक्तिगत ध्यान के साथ शिक्षा",
    aboutText:
      "हर छात्र का एक मेंटर है, हर कक्षा की समय-सारणी और उपस्थिति ऑनलाइन है, और हर परिणाम, रसीद और प्रमाणपत्र छात्रों और अभिभावकों से बस एक क्लिक दूर है।",
    pillars: [
      { title: "परवाह करने वाली पढ़ाई", text: "मेंटर उपस्थिति और अंकों पर नज़र रखते हैं और ज़रूरत पड़ने पर जल्दी मदद करते हैं।" },
      { title: "समय पर परीक्षा", text: "परीक्षा फॉर्म, हॉल टिकट और परिणाम ऑनलाइन, विश्वविद्यालय के नियमों के साथ।" },
      { title: "पारदर्शी शुल्क", text: "ऑनलाइन भुगतान करें, तुरंत रसीद पाएं, और अपने विवरण में हर रुपया देखें।" },
      { title: "बिना कतार के प्रमाणपत्र", text: "बोनाफाइड और अन्य प्रमाणपत्र ऑनलाइन मांगें, हर एक पर QR कोड जिसे कोई भी जांच सकता है।" },
    ],
    academicsEyebrow: "शिक्षा",
    academicsTitle: "हमारे पाठ्यक्रम",
    academicsText: "विश्वविद्यालय से संबद्ध स्नातक पाठ्यक्रम, अनुभवी शिक्षकों द्वारा।",
    years: (n) => `${n} वर्ष`,
    noProgrammes: "पाठ्यक्रम जल्द ही यहाँ दिखेंगे।",
    campusEyebrow: "कैंपस जीवन",
    campusTitle: "कक्षा से कहीं अधिक",
    campusItems: [
      { key: "library", title: "पुस्तकालय", text: "हज़ारों किताबें, ऑनलाइन आरक्षण और लौटाने की तारीख से पहले याद दिलाना।" },
      { key: "hostel", title: "छात्रावास", text: "सुरक्षित कमरे, साप्ताहिक मेस मेन्यू, आउट-पास पर अभिभावकों को तुरंत सूचना।" },
      { key: "placement", title: "प्लेसमेंट", text: "कैंपस ड्राइव, आपकी पात्रता की जांच और ऑफ़र एक ही जगह।" },
      { key: "exams", title: "परीक्षा और परिणाम", text: "हॉल टिकट, परिणाम, SGPA और CGPA, और पुनर्मूल्यांकन ऑनलाइन।" },
      { key: "scholarship", title: "छात्रवृत्ति", text: "देखें कि आप किन छात्रवृत्तियों के लिए आवेदन कर सकते हैं, और कोई अंतिम तिथि न चूकें।" },
      { key: "care", title: "छात्र सहायता", text: "शिकायत दर्ज करें, चाहें तो गुमनाम रूप से, और समय पर उत्तर पाएं।" },
    ],
    admissionsTitle: "प्रवेश ऑनलाइन है",
    admissionsText: "कुछ ही मिनटों में अपने फ़ोन से आवेदन करें। न फॉर्म छापने हैं, न कतारें।",
    admissionsSteps: ["अपने मोबाइल नंबर से साइन इन करें", "फॉर्म भरें और दस्तावेज़ अपलोड करें", "शुल्क भरें और अपना आवेदन ट्रैक करें"],
    portalsEyebrow: "पोर्टल",
    portalsTitle: "पूरे कॉलेज के लिए एक लॉगिन",
    portals: [
      { key: "student", title: "छात्र", text: "शुल्क, उपस्थिति, अंक, परिणाम, प्रमाणपत्र और सूचनाएं।", action: "छात्र लॉगिन" },
      { key: "staff", title: "कर्मचारी", text: "कार्यालय, लेखा, अध्यापन, परीक्षा, पुस्तकालय, छात्रावास और प्लेसमेंट।", action: "कर्मचारी लॉगिन" },
      { key: "parent", title: "अभिभावक", text: "आपके बच्चे का शुल्क, उपस्थिति और परिणाम, मोबाइल पर आए कोड से।", action: "अभिभावक लॉगिन" },
    ],
    aiTitle: "CollegeConnect AI से पूछें",
    aiText: "और जानकारी चाहिए? शुल्क, परीक्षा, प्रवेश या किसी भी सूचना के बारे में English, हिंदी या मराठी में पूछें। शुरू करने के लिए लॉगिन करें।",
    aiAction: "पूछने के लिए लॉगिन करें",
    aiOpen: "पूछने के लिए मेरा पोर्टल खोलें",
    verify: "हमसे कोई प्रमाणपत्र या रसीद मिली है? असली है या नहीं, जानने के लिए उसका QR कोड स्कैन करें।",
    affiliated: "संबद्ध",
    footer: "आपका डेटा केवल आपको और ज़रूरी कर्मचारियों को दिखता है।",
  },
  mr: {
    nav: { about: "परिचय", academics: "शिक्षण", campus: "कॅम्पस जीवन", admissions: "प्रवेश" },
    login: "लॉगिन",
    goToPortal: "माझ्या पोर्टलवर जा",
    collegeFallback: "आमचे महाविद्यालय",
    heroEyebrow: "स्वागत आहे",
    heroWords: ["शिका.", "वाढा.", "जोडा."],
    heroText: "शिकण्याची, शोधण्याची आणि भविष्य घडवण्याची जागा — तुम्हाला नावाने ओळखणारे शिक्षक आणि ऑनलाइन चालणारे कॅम्पस.",
    apply: "प्रवेशासाठी अर्ज",
    explore: "महाविद्यालय पाहा",
    stats: { programmes: "अभ्यासक्रम", departments: "विभाग", languages: "भाषा", online: "ऑनलाइन सेवा" },
    aboutEyebrow: "महाविद्यालयाविषयी",
    aboutTitle: "वैयक्तिक लक्ष देणारे शिक्षण",
    aboutText:
      "प्रत्येक विद्यार्थ्याला एक मेंटॉर आहे, प्रत्येक वर्गाचे वेळापत्रक आणि उपस्थिती ऑनलाइन आहे, आणि प्रत्येक निकाल, पावती व प्रमाणपत्र विद्यार्थी व पालकांपासून एका क्लिकवर आहे.",
    pillars: [
      { title: "काळजी घेणारे अध्यापन", text: "मेंटॉर उपस्थिती आणि गुणांवर लक्ष ठेवतात आणि गरज असेल तेव्हा लवकर मदत करतात." },
      { title: "वेळेवर परीक्षा", text: "परीक्षा अर्ज, हॉल तिकीट आणि निकाल ऑनलाइन, विद्यापीठाच्या नियमांसह." },
      { title: "पारदर्शक शुल्क", text: "ऑनलाइन भरा, लगेच पावती मिळवा, आणि तुमच्या विवरणात प्रत्येक रुपया पाहा." },
      { title: "रांगेशिवाय प्रमाणपत्रे", text: "बोनाफाईड व इतर प्रमाणपत्रे ऑनलाइन मागा, प्रत्येकावर कोणीही तपासू शकेल असा QR कोड." },
    ],
    academicsEyebrow: "शिक्षण",
    academicsTitle: "आमचे अभ्यासक्रम",
    academicsText: "विद्यापीठाशी संलग्न पदवी अभ्यासक्रम, अनुभवी प्राध्यापकांकडून.",
    years: (n) => `${n} वर्षे`,
    noProgrammes: "अभ्यासक्रम लवकरच येथे दिसतील.",
    campusEyebrow: "कॅम्पस जीवन",
    campusTitle: "वर्गाच्या पलीकडे",
    campusItems: [
      { key: "library", title: "ग्रंथालय", text: "हजारो पुस्तके, ऑनलाइन आरक्षण आणि परत करण्याच्या तारखेपूर्वी आठवण." },
      { key: "hostel", title: "वसतिगृह", text: "सुरक्षित खोल्या, साप्ताहिक मेस मेन्यू, आउट-पासवर पालकांना लगेच कळवले जाते." },
      { key: "placement", title: "प्लेसमेंट", text: "कॅम्पस ड्राइव्ह, तुमची पात्रता तपासली जाते आणि ऑफर्स एकाच ठिकाणी." },
      { key: "exams", title: "परीक्षा आणि निकाल", text: "हॉल तिकीट, निकाल, SGPA व CGPA, आणि पुनर्मूल्यांकन ऑनलाइन." },
      { key: "scholarship", title: "शिष्यवृत्ती", text: "तुम्ही कोणत्या शिष्यवृत्तीसाठी अर्ज करू शकता ते पाहा, आणि एकही अंतिम तारीख चुकवू नका." },
      { key: "care", title: "विद्यार्थी सहाय्य", text: "तक्रार नोंदवा, हवे तर नाव न सांगता, आणि वेळेवर उत्तर मिळवा." },
    ],
    admissionsTitle: "प्रवेश ऑनलाइन आहे",
    admissionsText: "काही मिनिटांत तुमच्या फोनवरून अर्ज करा. फॉर्म छापायचे नाहीत, रांगा नाहीत.",
    admissionsSteps: ["तुमच्या मोबाइल नंबरने साइन इन करा", "फॉर्म भरा आणि कागदपत्रे अपलोड करा", "शुल्क भरा आणि अर्जाची स्थिती पाहा"],
    portalsEyebrow: "पोर्टल",
    portalsTitle: "संपूर्ण महाविद्यालयासाठी एक लॉगिन",
    portals: [
      { key: "student", title: "विद्यार्थी", text: "शुल्क, उपस्थिती, गुण, निकाल, प्रमाणपत्रे आणि सूचना.", action: "विद्यार्थी लॉगिन" },
      { key: "staff", title: "कर्मचारी", text: "कार्यालय, लेखा, अध्यापन, परीक्षा, ग्रंथालय, वसतिगृह आणि प्लेसमेंट.", action: "कर्मचारी लॉगिन" },
      { key: "parent", title: "पालक", text: "तुमच्या पाल्याचे शुल्क, उपस्थिती आणि निकाल, मोबाइलवर आलेल्या कोडने.", action: "पालक लॉगिन" },
    ],
    aiTitle: "CollegeConnect AI ला विचारा",
    aiText: "अधिक माहिती हवी आहे? शुल्क, परीक्षा, प्रवेश किंवा कोणत्याही सूचनेबद्दल English, हिंदी किंवा मराठीत विचारा. सुरू करण्यासाठी लॉगिन करा.",
    aiAction: "विचारण्यासाठी लॉगिन करा",
    aiOpen: "विचारण्यासाठी माझे पोर्टल उघडा",
    verify: "आमच्याकडून प्रमाणपत्र किंवा पावती मिळाली आहे? ती खरी आहे का ते पाहण्यासाठी तिचा QR कोड स्कॅन करा.",
    affiliated: "संलग्न",
    footer: "तुमचा डेटा फक्त तुम्हाला आणि गरज असलेल्या कर्मचाऱ्यांना दिसतो.",
  },
};
