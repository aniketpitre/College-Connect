import type { Category, Language } from "./types";

export interface Dept {
  category: Category;
  mark: string;
  title: string;
  desc: string;
}

export interface Strings {
  nav_features: string;
  nav_how: string;
  nav_demo: string;
  nav_dash: string;
  hero_eyebrow: string;
  hero_h1_plain: string;
  hero_h1_em: string;
  hero_lede: string;
  hero_cta1: string;
  hero_cta2: string;
  stat1: string;
  stat2: string;
  stat3: string;
  card_tag: string;
  card_stamp: string;
  heroPreview: { user: string; bot: string; cite: string };
  ledger: [string, string, string, string];
  dept_eyebrow: string;
  dept_h2: string;
  dept_p: string;
  dept_ask: string;
  depts: Dept[];
  how_eyebrow: string;
  how_h2: string;
  how_p: string;
  flow: { title: string; desc: string }[];
  demo_eyebrow: string;
  demo_h2: string;
  demo_p: string;
  demo_side_h: string;
  demo_side_p: string;
  chips: string[];
  demo_placeholder: string;
  demo_send: string;
  welcome: string;
  filtering: string;
  clearFilter: string;
  allTopics: string;
  thinking: string;
  source: string;
  confidence: string;
  grounded: string;
  notGrounded: string;
  backendOffline: string;
  dash_eyebrow: string;
  dash_h2: string;
  dash_p: string;
  dash_preview: string;
  dash1_eyebrow: string;
  dash1_h: string;
  dash1_p: string;
  dash1_rows: [string, string][];
  dash2_eyebrow: string;
  dash2_h: string;
  dash2_p: string;
  dash2_rows: [string, string][];
  dash2_link: string;
  footer_note: string;
}

export const UI_STRINGS: Record<Language, Strings> = {
  en: {
    nav_features: "Departments",
    nav_how: "How it works",
    nav_demo: "Try it",
    nav_dash: "Dashboards",
    hero_eyebrow: "Digital Registrar's Office",
    hero_h1_plain: "Every answer, ",
    hero_h1_em: "stamped from the source.",
    hero_lede:
      "Ask about admissions, fees, timetables, exams or placements — CollegeConnect AI answers instantly, in English, Hindi or Marathi, and cites exactly which college document it came from.",
    hero_cta1: "Ask a question",
    hero_cta2: "See how it works",
    stat1: "Always answering",
    stat2: "Languages supported",
    stat3: "Answers cite their source",
    card_tag: "Live query",
    card_stamp: "Verified source",
    heroPreview: {
      user: "What's the last date to pay semester fees?",
      bot: "Odd-semester tuition fees are due by 10 August 2026. After that, a late fee of Rs. 500 per week applies.",
      cite: "Source: Fee Structure & Payment Schedule 2026 · Section 2",
    },
    ledger: ["Admissions & scholarships", "Fees & accounts", "Timetables & exams", "Placements & notices"],
    dept_eyebrow: "Who's on call",
    dept_h2: "One assistant, every office.",
    dept_p:
      "CollegeConnect AI stands in for the desks students queue at most — pulling straight from the documents each office already publishes.",
    dept_ask: "Ask this office →",
    depts: [
      { category: "admissions", mark: "Office 01", title: "Admissions", desc: "Eligibility, application steps, deadlines and scholarship criteria." },
      { category: "fees", mark: "Office 02", title: "Accounts", desc: "Fee structure, due dates, payment status and refund policy." },
      { category: "examinations", mark: "Office 03", title: "Exam cell", desc: "Timetables, hall tickets, syllabus and result dates." },
      { category: "placements", mark: "Office 04", title: "Placement cell", desc: "Drives, eligibility criteria and past placement records." },
      { category: "hostel", mark: "Office 05", title: "Hostel & campus", desc: "Room allotment, mess menu, library hours and facilities." },
      { category: "notices", mark: "Office 06", title: "Notice board", desc: "Circulars, event announcements and holiday calendars." },
    ],
    how_eyebrow: "The pipeline",
    how_h2: "Ask, retrieve, cite.",
    how_p: "Every reply is traced back to an actual document — never a guess.",
    flow: [
      { title: "Ask in plain language", desc: "Type a question in English, Hindi or Marathi." },
      { title: "Retrieve the right document", desc: "The system searches official college documents for the most relevant passages." },
      { title: "Answer, with citation", desc: "You get a direct answer plus the document and section it came from." },
    ],
    demo_eyebrow: "Live assistant",
    demo_h2: "Try the assistant.",
    demo_p: "Answers are generated live from the college's official documents, with the source shown under each reply.",
    demo_side_h: "Quick questions",
    demo_side_p: "Tap one, or type your own below.",
    chips: [
      "What documents do I need for admission?",
      "What's the hostel fee?",
      "When are the odd semester exams?",
      "When is the next placement drive?",
    ],
    demo_placeholder: "Ask about fees, hostel, exams…",
    demo_send: "Send",
    welcome:
      "Hi! I'm CollegeConnect AI. Ask me anything about admissions, fees, exams, placements, hostel or notices — I'll answer from official college documents and show you the source.",
    filtering: "Searching only:",
    clearFilter: "Show all",
    allTopics: "All offices",
    thinking: "Searching official documents…",
    source: "Source",
    confidence: "Confidence",
    grounded: "Grounded in official document",
    notGrounded: "No matching document found",
    backendOffline: "Could not reach the CollegeConnect server. Please try again in a moment.",
    dash_eyebrow: "Behind the login",
    dash_h2: "Two dashboards, built for the reader.",
    dash_p: "Students see their own record. Administrators see the whole campus.",
    dash_preview: "Preview · sample data",
    dash1_eyebrow: "Student portal",
    dash1_h: "My record",
    dash1_p: "Attendance, timetable, fee status, assignments and results in one place.",
    dash1_rows: [["Attendance", "86%"], ["Fee status", "Paid"], ["Next exam", "25 Nov"]],
    dash2_eyebrow: "Admin portal",
    dash2_h: "Campus overview",
    dash2_p: "Manage notices, documents, the chatbot's knowledge base, and usage analytics.",
    dash2_rows: [["Queries this week", "4,208"], ["Documents indexed", "132"], ["Open notices", "7"]],
    dash2_link: "Open the admin portal →",
    footer_note: "Answers come from approved college documents. Always confirm important deadlines with the cited source.",
  },
  hi: {
    nav_features: "विभाग",
    nav_how: "यह कैसे काम करता है",
    nav_demo: "आज़माएं",
    nav_dash: "डैशबोर्ड",
    hero_eyebrow: "डिजिटल रजिस्ट्रार कार्यालय",
    hero_h1_plain: "हर जवाब, ",
    hero_h1_em: "स्रोत से प्रमाणित।",
    hero_lede:
      "प्रवेश, फीस, समय-सारणी, परीक्षा या प्लेसमेंट के बारे में पूछें — CollegeConnect AI तुरंत उत्तर देता है, अंग्रेज़ी, हिंदी या मराठी में, और बताता है कि यह किस दस्तावेज़ से लिया गया है।",
    hero_cta1: "सवाल पूछें",
    hero_cta2: "जानें कैसे काम करता है",
    stat1: "हमेशा उपलब्ध",
    stat2: "भाषाएं समर्थित",
    stat3: "हर उत्तर के साथ स्रोत",
    card_tag: "लाइव प्रश्न",
    card_stamp: "सत्यापित स्रोत",
    heroPreview: {
      user: "सेमेस्टर फीस भरने की आखिरी तारीख क्या है?",
      bot: "विषम सेमेस्टर की ट्यूशन फीस 10 अगस्त 2026 तक भरनी है। उसके बाद ₹500 प्रति सप्ताह विलंब शुल्क लगेगा।",
      cite: "स्रोत: फीस संरचना एवं भुगतान अनुसूची 2026 · खंड 2",
    },
    ledger: ["प्रवेश और छात्रवृत्ति", "फीस और खाते", "समय-सारणी और परीक्षा", "प्लेसमेंट और सूचनाएं"],
    dept_eyebrow: "कौन ज़िम्मेदार है",
    dept_h2: "एक सहायक, हर कार्यालय के लिए।",
    dept_p: "CollegeConnect AI उन डेस्कों की जगह लेता है जहां छात्र सबसे ज़्यादा कतार लगाते हैं — सीधे हर कार्यालय के दस्तावेज़ों से।",
    dept_ask: "इस कार्यालय से पूछें →",
    depts: [
      { category: "admissions", mark: "कार्यालय 01", title: "प्रवेश", desc: "पात्रता, आवेदन चरण, समय-सीमा और छात्रवृत्ति मानदंड।" },
      { category: "fees", mark: "कार्यालय 02", title: "लेखा", desc: "फीस संरचना, देय तिथियां, भुगतान स्थिति और वापसी नीति।" },
      { category: "examinations", mark: "कार्यालय 03", title: "परीक्षा प्रकोष्ठ", desc: "समय-सारणी, हॉल टिकट, पाठ्यक्रम और परिणाम तिथियां।" },
      { category: "placements", mark: "कार्यालय 04", title: "प्लेसमेंट सेल", desc: "ड्राइव, पात्रता मानदंड और पिछले प्लेसमेंट रिकॉर्ड।" },
      { category: "hostel", mark: "कार्यालय 05", title: "हॉस्टल और कैंपस", desc: "कमरा आवंटन, मेस मेन्यू, पुस्तकालय समय और सुविधाएं।" },
      { category: "notices", mark: "कार्यालय 06", title: "सूचना बोर्ड", desc: "परिपत्र, कार्यक्रम घोषणाएं और अवकाश कैलेंडर।" },
    ],
    how_eyebrow: "प्रक्रिया",
    how_h2: "पूछें, खोजें, प्रमाणित करें।",
    how_p: "हर उत्तर किसी वास्तविक दस्तावेज़ से जुड़ा होता है — कभी अंदाज़ा नहीं।",
    flow: [
      { title: "सामान्य भाषा में पूछें", desc: "अंग्रेज़ी, हिंदी या मराठी में सवाल लिखें।" },
      { title: "सही दस्तावेज़ खोजें", desc: "सिस्टम आधिकारिक कॉलेज दस्तावेज़ों में सबसे प्रासंगिक अंश खोजता है।" },
      { title: "उत्तर, स्रोत के साथ", desc: "आपको सीधा उत्तर मिलता है, साथ ही वह दस्तावेज़ और खंड भी।" },
    ],
    demo_eyebrow: "लाइव सहायक",
    demo_h2: "सहायक को आज़माएं।",
    demo_p: "उत्तर कॉलेज के आधिकारिक दस्तावेज़ों से लाइव तैयार किए जाते हैं, और हर उत्तर के नीचे स्रोत दिखाया जाता है।",
    demo_side_h: "त्वरित प्रश्न",
    demo_side_p: "किसी एक पर टैप करें, या नीचे अपना प्रश्न टाइप करें।",
    chips: ["प्रवेश के लिए कौन से दस्तावेज़ चाहिए?", "हॉस्टल फीस कितनी है?", "विषम सेमेस्टर की परीक्षाएं कब हैं?", "अगली प्लेसमेंट ड्राइव कब है?"],
    demo_placeholder: "फीस, हॉस्टल, परीक्षा के बारे में पूछें…",
    demo_send: "भेजें",
    welcome:
      "नमस्ते! मैं कॉलेजकनेक्ट AI हूं। प्रवेश, शुल्क, परीक्षा, प्लेसमेंट, छात्रावास या सूचनाओं के बारे में कुछ भी पूछें — मैं आधिकारिक कॉलेज दस्तावेज़ों से उत्तर दूंगा और स्रोत दिखाऊंगा।",
    filtering: "केवल खोज:",
    clearFilter: "सभी दिखाएं",
    allTopics: "सभी कार्यालय",
    thinking: "आधिकारिक दस्तावेज़ खोजे जा रहे हैं…",
    source: "स्रोत",
    confidence: "विश्वास स्तर",
    grounded: "आधिकारिक दस्तावेज़ पर आधारित",
    notGrounded: "कोई मिलान दस्तावेज़ नहीं मिला",
    backendOffline: "कॉलेजकनेक्ट सर्वर तक नहीं पहुंच सका। कृपया थोड़ी देर बाद पुनः प्रयास करें।",
    dash_eyebrow: "लॉगिन के पीछे",
    dash_h2: "दो डैशबोर्ड, पाठक के लिए बनाए गए।",
    dash_p: "छात्र अपना रिकॉर्ड देखते हैं। प्रशासक पूरा कैंपस देखते हैं।",
    dash_preview: "पूर्वावलोकन · नमूना डेटा",
    dash1_eyebrow: "छात्र पोर्टल",
    dash1_h: "मेरा रिकॉर्ड",
    dash1_p: "उपस्थिति, समय-सारणी, फीस स्थिति, असाइनमेंट और परिणाम एक ही जगह।",
    dash1_rows: [["उपस्थिति", "86%"], ["फीस स्थिति", "भुगतान हुआ"], ["अगली परीक्षा", "25 नवंबर"]],
    dash2_eyebrow: "एडमिन पोर्टल",
    dash2_h: "कैंपस अवलोकन",
    dash2_p: "सूचनाएं, दस्तावेज़, चैटबॉट का ज्ञान आधार, और उपयोग विश्लेषण प्रबंधित करें।",
    dash2_rows: [["इस सप्ताह के प्रश्न", "4,208"], ["अनुक्रमित दस्तावेज़", "132"], ["खुली सूचनाएं", "7"]],
    dash2_link: "एडमिन पोर्टल खोलें →",
    footer_note: "उत्तर आधिकारिक कॉलेज दस्तावेज़ों से तैयार किए जाते हैं। महत्वपूर्ण समय-सीमाओं के लिए हमेशा उद्धृत स्रोत देखें।",
  },
  mr: {
    nav_features: "विभाग",
    nav_how: "हे कसे कार्य करते",
    nav_demo: "वापरून पहा",
    nav_dash: "डॅशबोर्ड",
    hero_eyebrow: "डिजिटल रजिस्ट्रार कार्यालय",
    hero_h1_plain: "प्रत्येक उत्तर, ",
    hero_h1_em: "स्रोतावरून प्रमाणित.",
    hero_lede:
      "प्रवेश, फी, वेळापत्रक, परीक्षा किंवा प्लेसमेंटबद्दल विचारा — CollegeConnect AI त्वरित उत्तर देते, इंग्रजी, हिंदी किंवा मराठीत, आणि हे कोणत्या कागदपत्रातून घेतले आहे ते सांगते.",
    hero_cta1: "प्रश्न विचारा",
    hero_cta2: "हे कसे कार्य करते ते पहा",
    stat1: "नेहमी उपलब्ध",
    stat2: "समर्थित भाषा",
    stat3: "प्रत्येक उत्तरासोबत स्रोत",
    card_tag: "थेट प्रश्न",
    card_stamp: "सत्यापित स्रोत",
    heroPreview: {
      user: "सत्र फी भरण्याची शेवटची तारीख कोणती आहे?",
      bot: "विषम सत्राची शिक्षण फी 10 ऑगस्ट 2026 पर्यंत भरावी लागेल. त्यानंतर दर आठवड्याला ₹500 विलंब शुल्क लागू होईल.",
      cite: "स्रोत: फी रचना व भरणा वेळापत्रक 2026 · विभाग 2",
    },
    ledger: ["प्रवेश व शिष्यवृत्ती", "फी व खाती", "वेळापत्रक व परीक्षा", "प्लेसमेंट व सूचना"],
    dept_eyebrow: "जबाबदार कोण",
    dept_h2: "एक सहाय्यक, प्रत्येक कार्यालयासाठी.",
    dept_p: "CollegeConnect AI त्या डेस्कची जागा घेते जिथे विद्यार्थी सर्वाधिक रांगेत उभे राहतात — प्रत्येक कार्यालयाच्या कागदपत्रांतून थेट.",
    dept_ask: "या कार्यालयाला विचारा →",
    depts: [
      { category: "admissions", mark: "कार्यालय 01", title: "प्रवेश", desc: "पात्रता, अर्ज प्रक्रिया, मुदत आणि शिष्यवृत्ती निकष." },
      { category: "fees", mark: "कार्यालय 02", title: "लेखा", desc: "फी रचना, देय तारखा, पेमेंट स्थिती आणि परतावा धोरण." },
      { category: "examinations", mark: "कार्यालय 03", title: "परीक्षा कक्ष", desc: "वेळापत्रक, हॉल तिकीट, अभ्यासक्रम आणि निकाल तारखा." },
      { category: "placements", mark: "कार्यालय 04", title: "प्लेसमेंट सेल", desc: "ड्राइव्ह, पात्रता निकष आणि मागील प्लेसमेंट रेकॉर्ड." },
      { category: "hostel", mark: "कार्यालय 05", title: "वसतिगृह व कॅम्पस", desc: "खोली वाटप, मेस मेनू, ग्रंथालय वेळा आणि सुविधा." },
      { category: "notices", mark: "कार्यालय 06", title: "सूचना फलक", desc: "परिपत्रके, कार्यक्रम घोषणा आणि सुट्टी दिनदर्शिका." },
    ],
    how_eyebrow: "प्रक्रिया",
    how_h2: "विचारा, शोधा, प्रमाणित करा.",
    how_p: "प्रत्येक उत्तर प्रत्यक्ष कागदपत्राशी जोडलेले असते — कधीही अंदाज नाही.",
    flow: [
      { title: "सोप्या भाषेत विचारा", desc: "इंग्रजी, हिंदी किंवा मराठीत प्रश्न टाइप करा." },
      { title: "योग्य कागदपत्र शोधा", desc: "प्रणाली अधिकृत कॉलेज कागदपत्रांमध्ये सर्वात संबंधित भाग शोधते." },
      { title: "उत्तर, स्रोतासह", desc: "तुम्हाला थेट उत्तर मिळते, तसेच ते कागदपत्र व विभाग." },
    ],
    demo_eyebrow: "थेट सहाय्यक",
    demo_h2: "सहाय्यक वापरून पहा.",
    demo_p: "उत्तरे महाविद्यालयाच्या अधिकृत कागदपत्रांतून थेट तयार केली जातात, आणि प्रत्येक उत्तराखाली स्रोत दाखवला जातो.",
    demo_side_h: "जलद प्रश्न",
    demo_side_p: "एकावर टॅप करा, किंवा खाली स्वतःचा प्रश्न टाइप करा.",
    chips: ["प्रवेशासाठी कोणती कागदपत्रे लागतात?", "वसतिगृह फी किती आहे?", "विषम सत्राच्या परीक्षा कधी आहेत?", "पुढील प्लेसमेंट ड्राइव्ह कधी आहे?"],
    demo_placeholder: "फी, वसतिगृह, परीक्षा याबद्दल विचारा…",
    demo_send: "पाठवा",
    welcome:
      "नमस्कार! मी कॉलेजकनेक्ट AI आहे. प्रवेश, शुल्क, परीक्षा, प्लेसमेंट, वसतिगृह किंवा सूचनांबद्दल काहीही विचारा — मी अधिकृत महाविद्यालयीन दस्तऐवजांमधून उत्तर देईन आणि स्रोत दाखवेन.",
    filtering: "फक्त शोध:",
    clearFilter: "सर्व दाखवा",
    allTopics: "सर्व कार्यालये",
    thinking: "अधिकृत दस्तऐवज शोधले जात आहेत…",
    source: "स्रोत",
    confidence: "विश्वासार्हता",
    grounded: "अधिकृत दस्तऐवजावर आधारित",
    notGrounded: "जुळणारा दस्तऐवज सापडला नाही",
    backendOffline: "कॉलेजकनेक्ट सर्व्हरशी संपर्क होऊ शकला नाही. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.",
    dash_eyebrow: "लॉगिनच्या मागे",
    dash_h2: "दोन डॅशबोर्ड, वाचकासाठी तयार केलेले.",
    dash_p: "विद्यार्थी स्वतःचा रेकॉर्ड पाहतात. प्रशासक संपूर्ण कॅम्पस पाहतात.",
    dash_preview: "पूर्वावलोकन · नमुना डेटा",
    dash1_eyebrow: "विद्यार्थी पोर्टल",
    dash1_h: "माझा रेकॉर्ड",
    dash1_p: "उपस्थिती, वेळापत्रक, फी स्थिती, असाइनमेंट व निकाल एका ठिकाणी.",
    dash1_rows: [["उपस्थिती", "86%"], ["फी स्थिती", "भरली"], ["पुढील परीक्षा", "25 नोव्हेंबर"]],
    dash2_eyebrow: "अ‍ॅडमिन पोर्टल",
    dash2_h: "कॅम्पस आढावा",
    dash2_p: "सूचना, कागदपत्रे, चॅटबॉटचा ज्ञानसंच, आणि वापर विश्लेषण व्यवस्थापित करा.",
    dash2_rows: [["या आठवड्यातील प्रश्न", "4,208"], ["अनुक्रमित कागदपत्रे", "132"], ["खुल्या सूचना", "7"]],
    dash2_link: "अ‍ॅडमिन पोर्टल उघडा →",
    footer_note: "उत्तरे अधिकृत महाविद्यालयीन दस्तऐवजांमधून तयार केली जातात. महत्त्वाच्या मुदतींसाठी नेहमी उद्धृत स्रोत तपासा.",
  },
};
