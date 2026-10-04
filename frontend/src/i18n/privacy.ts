import type { Language } from "../lib/types";

/** Must match PRIVACY_VERSION in backend/app/modules/onboarding/service.py. Change both together. */
export const PRIVACY_VERSION = "2026-10";

interface Section {
  title: string;
  body: string;
}

/** Privacy notice for students (DPDP Act 2023 and Rules 2025), shown at first sign-in. */
export const PRIVACY_NOTICE: Record<Language, { title: string; intro: string; sections: Section[] }> = {
  en: {
    title: "Privacy notice",
    intro: "Your college keeps the information below to run your admission, studies and exams. This notice says what we hold, why, and your rights.",
    sections: [
      { title: "What we hold", body: "Your name, photo, date of birth, gender, contact details, parent/guardian details, address, category, the last 4 digits of your Aadhaar, APAAR/ABC ID, previous marks and documents you or the office upload, your course and class, fees and receipts, attendance and marks." },
      { title: "Why", body: "To admit and enrol you, teach and assess you, run exams and results, collect fees and issue receipts and certificates, apply for scholarships on your behalf, keep you safe, and send records the university and government require by law." },
      { title: "Who sees it", body: "Only college staff who need it for their work, you, and (from a later phase) a parent or guardian linked to your account. We share it only with the university, scholarship portals and government bodies where the law requires. We never sell it or use it for advertising." },
      { title: "How long", body: "For as long as university and government rules require for student records. Help-desk questions are kept for one year and never store your personal record." },
      { title: "Your rights", body: "You can see your data and download a copy, ask for corrections (My profile → Request a correction), and raise a complaint with the college office. If you are under 18, your parent or guardian gives consent at the college office." },
    ],
  },
  hi: {
    title: "गोपनीयता सूचना",
    intro: "आपका कॉलेज आपके प्रवेश, पढ़ाई और परीक्षाओं के लिए नीचे दी गई जानकारी रखता है। यह सूचना बताती है कि हम क्या रखते हैं, क्यों, और आपके अधिकार क्या हैं।",
    sections: [
      { title: "हम क्या रखते हैं", body: "आपका नाम, फ़ोटो, जन्म तिथि, लिंग, संपर्क विवरण, माता-पिता/अभिभावक का विवरण, पता, श्रेणी, आधार के अंतिम 4 अंक, APAAR/ABC आईडी, पिछले अंक और आपके या कार्यालय द्वारा अपलोड किए गए दस्तावेज़, आपका पाठ्यक्रम और कक्षा, फ़ीस और रसीदें, उपस्थिति और अंक।" },
      { title: "क्यों", body: "आपको प्रवेश देने और नामांकित करने, पढ़ाने और मूल्यांकन करने, परीक्षाएं और परिणाम चलाने, फ़ीस लेने और रसीदें व प्रमाणपत्र देने, आपकी ओर से छात्रवृत्ति के लिए आवेदन करने, आपको सुरक्षित रखने, और कानून के अनुसार विश्वविद्यालय व सरकार को रिकॉर्ड भेजने के लिए।" },
      { title: "इसे कौन देखता है", body: "केवल वे कॉलेज कर्मचारी जिन्हें काम के लिए इसकी ज़रूरत है, आप, और (बाद के चरण से) आपके खाते से जुड़े माता-पिता या अभिभावक। हम इसे केवल वहीं साझा करते हैं जहां कानून के अनुसार ज़रूरी है: विश्वविद्यालय, छात्रवृत्ति पोर्टल और सरकारी संस्थाएं। हम इसे कभी नहीं बेचते और न ही विज्ञापन के लिए उपयोग करते हैं।" },
      { title: "कितने समय तक", body: "जितने समय तक विश्वविद्यालय और सरकारी नियम छात्र रिकॉर्ड रखने को कहते हैं। हेल्प डेस्क के प्रश्न एक वर्ष तक रखे जाते हैं और उनमें आपका व्यक्तिगत रिकॉर्ड कभी नहीं रखा जाता।" },
      { title: "आपके अधिकार", body: "आप अपना डेटा देख सकते हैं और उसकी प्रति डाउनलोड कर सकते हैं, सुधार का अनुरोध कर सकते हैं (मेरी प्रोफ़ाइल → सुधार का अनुरोध करें), और कॉलेज कार्यालय में शिकायत कर सकते हैं। यदि आपकी आयु 18 वर्ष से कम है, तो आपके माता-पिता या अभिभावक कॉलेज कार्यालय में सहमति देते हैं।" },
    ],
  },
  mr: {
    title: "गोपनीयता सूचना",
    intro: "तुमचे महाविद्यालय तुमचा प्रवेश, शिक्षण आणि परीक्षांसाठी खालील माहिती ठेवते. आम्ही काय ठेवतो, का, आणि तुमचे अधिकार काय आहेत हे ही सूचना सांगते.",
    sections: [
      { title: "आम्ही काय ठेवतो", body: "तुमचे नाव, फोटो, जन्मतारीख, लिंग, संपर्क तपशील, आई-वडील/पालकांचा तपशील, पत्ता, प्रवर्ग, आधारचे शेवटचे 4 अंक, APAAR/ABC आयडी, मागील गुण आणि तुम्ही किंवा कार्यालयाने अपलोड केलेली कागदपत्रे, तुमचा अभ्यासक्रम आणि वर्ग, शुल्क आणि पावत्या, उपस्थिती आणि गुण." },
      { title: "का", body: "तुम्हाला प्रवेश देणे आणि नोंदणी करणे, शिकवणे आणि मूल्यमापन करणे, परीक्षा आणि निकाल चालवणे, शुल्क घेणे आणि पावत्या व प्रमाणपत्रे देणे, तुमच्या वतीने शिष्यवृत्तीसाठी अर्ज करणे, तुम्हाला सुरक्षित ठेवणे, आणि कायद्यानुसार विद्यापीठ व सरकारला नोंदी पाठवणे यासाठी." },
      { title: "ही माहिती कोण पाहते", body: "फक्त ज्या महाविद्यालयीन कर्मचाऱ्यांना कामासाठी ती लागते ते, तुम्ही, आणि (पुढील टप्प्यापासून) तुमच्या खात्याशी जोडलेले आई-वडील किंवा पालक. कायद्याने आवश्यक असेल तिथेच आम्ही ती विद्यापीठ, शिष्यवृत्ती पोर्टल आणि सरकारी संस्थांना देतो. आम्ही ती कधीही विकत नाही किंवा जाहिरातीसाठी वापरत नाही." },
      { title: "किती काळ", body: "विद्यापीठ आणि सरकारी नियम विद्यार्थी नोंदी ठेवायला सांगतात तितका काळ. हेल्प डेस्कवरील प्रश्न एक वर्ष ठेवले जातात आणि त्यात तुमची वैयक्तिक नोंद कधीच ठेवली जात नाही." },
      { title: "तुमचे अधिकार", body: "तुम्ही तुमची माहिती पाहू शकता आणि तिची प्रत डाउनलोड करू शकता, दुरुस्तीची विनंती करू शकता (माझी प्रोफाइल → दुरुस्तीची विनंती करा), आणि महाविद्यालय कार्यालयात तक्रार करू शकता. तुमचे वय 18 पेक्षा कमी असल्यास, तुमचे आई-वडील किंवा पालक महाविद्यालय कार्यालयात संमती देतात." },
    ],
  },
};

export interface WelcomeStrings {
  title: string;
  steps: [string, string, string];
  contactIntro: string;
  phone: string;
  email: string;
  emailHint: string;
  next: string;
  back: string;
  accept: string;
  under18: string;
  languageIntro: string;
  finish: string;
  finishing: string;
}

export const WELCOME_STRINGS: Record<Language, WelcomeStrings> = {
  en: {
    title: "Welcome to CollegeConnect",
    steps: ["Your contact details", "Privacy notice", "Language"],
    contactIntro: "Check that the college can reach you. Fix anything that is wrong.",
    phone: "Your mobile number",
    email: "Your email (optional)",
    emailHint: "Used for password reset links and receipts.",
    next: "Next",
    back: "Back",
    accept: "I have read the privacy notice and agree that the college uses my information as described.",
    under18: "You are under 18: your parent or guardian also needs to give consent at the college office.",
    languageIntro: "Which language should CollegeConnect use? You can change it any time.",
    finish: "Finish",
    finishing: "Saving…",
  },
  hi: {
    title: "कॉलेजकनेक्ट में आपका स्वागत है",
    steps: ["आपका संपर्क विवरण", "गोपनीयता सूचना", "भाषा"],
    contactIntro: "जांचें कि कॉलेज आपसे संपर्क कर सकता है। जो गलत है उसे ठीक करें।",
    phone: "आपका मोबाइल नंबर",
    email: "आपका ईमेल (वैकल्पिक)",
    emailHint: "पासवर्ड रीसेट लिंक और रसीदों के लिए।",
    next: "आगे",
    back: "पीछे",
    accept: "मैंने गोपनीयता सूचना पढ़ ली है और सहमत हूं कि कॉलेज मेरी जानकारी का उपयोग बताए अनुसार करे।",
    under18: "आपकी आयु 18 वर्ष से कम है: आपके माता-पिता या अभिभावक को भी कॉलेज कार्यालय में सहमति देनी होगी।",
    languageIntro: "कॉलेजकनेक्ट किस भाषा में दिखे? आप इसे कभी भी बदल सकते हैं।",
    finish: "पूरा करें",
    finishing: "सहेजा जा रहा है…",
  },
  mr: {
    title: "कॉलेजकनेक्टमध्ये स्वागत आहे",
    steps: ["तुमचा संपर्क तपशील", "गोपनीयता सूचना", "भाषा"],
    contactIntro: "महाविद्यालय तुमच्याशी संपर्क करू शकते का ते तपासा. जे चुकीचे आहे ते दुरुस्त करा.",
    phone: "तुमचा मोबाइल नंबर",
    email: "तुमचा ईमेल (ऐच्छिक)",
    emailHint: "पासवर्ड रीसेट लिंक आणि पावत्यांसाठी.",
    next: "पुढे",
    back: "मागे",
    accept: "मी गोपनीयता सूचना वाचली आहे आणि महाविद्यालयाने माझी माहिती वर सांगितल्याप्रमाणे वापरण्यास मी संमती देतो/देते.",
    under18: "तुमचे वय 18 पेक्षा कमी आहे: तुमच्या आई-वडिलांनी किंवा पालकांनीही महाविद्यालय कार्यालयात संमती द्यायला हवी.",
    languageIntro: "कॉलेजकनेक्ट कोणत्या भाषेत दिसावे? तुम्ही ती कधीही बदलू शकता.",
    finish: "पूर्ण करा",
    finishing: "जतन होत आहे…",
  },
};
