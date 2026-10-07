import type { Language } from "../lib/types";

export interface HomeStrings {
  signIn: string;
  goToPortal: string;
  heroTitle: string;
  heroText: string;
  portalsTitle: string;
  panels: { key: "student" | "parent" | "staff" | "apply"; title: string; text: string; action: string }[];
  aiTitle: string;
  aiText: string;
  aiExamples: string[];
  aiLocked: string;
  aiSignIn: string;
  aiOpen: string;
  aiLanguages: string;
  verify: string;
  footer: string;
}

/** The public home page (students, parents and applicants read it in their language). */
export const HOME_STRINGS: Record<Language, HomeStrings> = {
  en: {
    signIn: "Sign in",
    goToPortal: "Go to my portal",
    heroTitle: "Your college, in one place",
    heroText: "Fees, attendance, exams, results, certificates, notices and more, for students, parents and staff.",
    portalsTitle: "Sign in to your portal",
    panels: [
      { key: "student", title: "Students", text: "Fees and receipts, attendance, marks and results, certificates, notices.", action: "Student sign in" },
      { key: "parent", title: "Parents", text: "Your child's fees, attendance and results, with a code sent to your mobile.", action: "Parent sign in" },
      { key: "staff", title: "Staff", text: "Office, accounts, teaching, exams, library, hostel, placement and more.", action: "Staff sign in" },
      { key: "apply", title: "New admission", text: "Apply online, upload documents and pay the application fee.", action: "Apply for admission" },
    ],
    aiTitle: "Ask CollegeConnect AI",
    aiText:
      "Ask about fees, exams, admissions, the hostel or any notice, and about your own record. Answers come only from the college's official documents and your own data, always with the source.",
    aiExamples: ["How much fee do I still owe?", "When are the semester exams?", "Is my bonafide certificate ready?"],
    aiLocked: "Sign in to use the assistant: it answers from your own record and the notices meant for you.",
    aiSignIn: "Sign in to ask",
    aiOpen: "Open my portal and tap Ask",
    aiLanguages: "Works in English, हिंदी and मराठी.",
    verify: "Got a certificate or receipt? Scan its QR code to check it is genuine.",
    footer: "CollegeConnect: the college's own system. Your data is visible only to you and the staff who need it.",
  },
  hi: {
    signIn: "साइन इन",
    goToPortal: "मेरे पोर्टल पर जाएं",
    heroTitle: "आपका कॉलेज, एक ही जगह",
    heroText: "शुल्क, उपस्थिति, परीक्षा, परिणाम, प्रमाणपत्र, सूचनाएं और बहुत कुछ — छात्रों, अभिभावकों और कर्मचारियों के लिए।",
    portalsTitle: "अपने पोर्टल में साइन इन करें",
    panels: [
      { key: "student", title: "छात्र", text: "शुल्क और रसीदें, उपस्थिति, अंक और परिणाम, प्रमाणपत्र, सूचनाएं।", action: "छात्र साइन इन" },
      { key: "parent", title: "अभिभावक", text: "आपके बच्चे का शुल्क, उपस्थिति और परिणाम, मोबाइल पर भेजे गए कोड से।", action: "अभिभावक साइन इन" },
      { key: "staff", title: "कर्मचारी", text: "कार्यालय, लेखा, अध्यापन, परीक्षा, पुस्तकालय, छात्रावास, प्लेसमेंट आदि।", action: "कर्मचारी साइन इन" },
      { key: "apply", title: "नया प्रवेश", text: "ऑनलाइन आवेदन करें, दस्तावेज़ अपलोड करें और आवेदन शुल्क भरें।", action: "प्रवेश के लिए आवेदन" },
    ],
    aiTitle: "CollegeConnect AI से पूछें",
    aiText:
      "शुल्क, परीक्षा, प्रवेश, छात्रावास या किसी भी सूचना के बारे में, और अपने रिकॉर्ड के बारे में पूछें। उत्तर केवल कॉलेज के आधिकारिक दस्तावेज़ों और आपके अपने डेटा से, हमेशा स्रोत के साथ।",
    aiExamples: ["मुझे अभी कितनी फीस भरनी है?", "सेमेस्टर परीक्षाएँ कब हैं?", "क्या मेरा बोनाफाइड प्रमाणपत्र तैयार है?"],
    aiLocked: "सहायक का उपयोग करने के लिए साइन इन करें: यह आपके अपने रिकॉर्ड और आपके लिए बनी सूचनाओं से उत्तर देता है।",
    aiSignIn: "पूछने के लिए साइन इन करें",
    aiOpen: "मेरा पोर्टल खोलें और ‘पूछें’ दबाएं",
    aiLanguages: "English, हिंदी और मराठी में उपलब्ध।",
    verify: "कोई प्रमाणपत्र या रसीद मिली है? असली है या नहीं, जानने के लिए उसका QR कोड स्कैन करें।",
    footer: "CollegeConnect: कॉलेज की अपनी प्रणाली। आपका डेटा केवल आपको और ज़रूरी कर्मचारियों को दिखता है।",
  },
  mr: {
    signIn: "साइन इन",
    goToPortal: "माझ्या पोर्टलवर जा",
    heroTitle: "तुमचे महाविद्यालय, एकाच ठिकाणी",
    heroText: "शुल्क, उपस्थिती, परीक्षा, निकाल, प्रमाणपत्रे, सूचना आणि बरेच काही — विद्यार्थी, पालक आणि कर्मचाऱ्यांसाठी.",
    portalsTitle: "तुमच्या पोर्टलमध्ये साइन इन करा",
    panels: [
      { key: "student", title: "विद्यार्थी", text: "शुल्क आणि पावत्या, उपस्थिती, गुण आणि निकाल, प्रमाणपत्रे, सूचना.", action: "विद्यार्थी साइन इन" },
      { key: "parent", title: "पालक", text: "तुमच्या पाल्याचे शुल्क, उपस्थिती आणि निकाल, मोबाइलवर आलेल्या कोडने.", action: "पालक साइन इन" },
      { key: "staff", title: "कर्मचारी", text: "कार्यालय, लेखा, अध्यापन, परीक्षा, ग्रंथालय, वसतिगृह, प्लेसमेंट इ.", action: "कर्मचारी साइन इन" },
      { key: "apply", title: "नवीन प्रवेश", text: "ऑनलाइन अर्ज करा, कागदपत्रे अपलोड करा आणि अर्ज शुल्क भरा.", action: "प्रवेशासाठी अर्ज" },
    ],
    aiTitle: "CollegeConnect AI ला विचारा",
    aiText:
      "शुल्क, परीक्षा, प्रवेश, वसतिगृह किंवा कोणत्याही सूचनेबद्दल, आणि तुमच्या स्वतःच्या नोंदीबद्दल विचारा. उत्तरे फक्त महाविद्यालयाच्या अधिकृत दस्तऐवज आणि तुमच्या स्वतःच्या माहितीतून, नेहमी स्रोतासह.",
    aiExamples: ["मला अजून किती फी भरायची आहे?", "सत्र परीक्षा कधी आहेत?", "माझे बोनाफाईड प्रमाणपत्र तयार आहे का?"],
    aiLocked: "सहाय्यक वापरण्यासाठी साइन इन करा: तो तुमची स्वतःची नोंद आणि तुमच्यासाठीच्या सूचनांमधून उत्तर देतो.",
    aiSignIn: "विचारण्यासाठी साइन इन करा",
    aiOpen: "माझे पोर्टल उघडा आणि ‘विचारा’ दाबा",
    aiLanguages: "English, हिंदी आणि मराठीत उपलब्ध.",
    verify: "प्रमाणपत्र किंवा पावती मिळाली आहे? ती खरी आहे का ते तपासण्यासाठी त्याचा QR कोड स्कॅन करा.",
    footer: "CollegeConnect: महाविद्यालयाची स्वतःची प्रणाली. तुमची माहिती फक्त तुम्हाला आणि आवश्यक कर्मचाऱ्यांनाच दिसते.",
  },
};
