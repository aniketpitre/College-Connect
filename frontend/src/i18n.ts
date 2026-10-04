import type { Category, Language } from "./types";

export interface Office {
  category: Category;
  title: string;
  desc: string;
  questions: [string, string];
}

export interface Strings {
  tagline: string;
  offices: string;
  allOffices: string;
  allOfficesDesc: string;
  admin: string;
  welcomeTitle: string;
  welcome: string;
  tryAsking: string;
  generalQuestions: string[];
  placeholder: string;
  send: string;
  newChat: string;
  askingOffice: string;
  thinking: string;
  source: string;
  confidence: string;
  grounded: string;
  notGrounded: string;
  backendOffline: string;
  disclaimer: string;
  officesList: Office[];
}

export const UI_STRINGS: Record<Language, Strings> = {
  en: {
    tagline: "College help desk",
    offices: "Offices",
    allOffices: "All offices",
    allOfficesDesc: "Search every document",
    admin: "Admin",
    welcomeTitle: "How can I help you today?",
    welcome:
      "Ask about admissions, fees, exams, placements, hostel or notices. Every answer comes from an official college document, and the source is shown below it.",
    tryAsking: "Try asking",
    generalQuestions: [
      "What documents do I need for admission?",
      "What's the hostel fee?",
      "When are the odd semester exams?",
      "When is the next placement drive?",
    ],
    placeholder: "Ask a question…",
    send: "Send",
    newChat: "New chat",
    askingOffice: "Asking:",
    thinking: "Searching official documents…",
    source: "Source",
    confidence: "Confidence",
    grounded: "From an official document",
    notGrounded: "No matching document",
    backendOffline: "Could not reach the CollegeConnect server. Please try again in a moment.",
    disclaimer: "Answers come from official college documents. Confirm important deadlines with the cited source.",
    officesList: [
      { category: "admissions", title: "Admissions", desc: "Eligibility, documents, deadlines", questions: ["What documents do I need for admission?", "What is the last date to apply?"] },
      { category: "fees", title: "Accounts & fees", desc: "Fee deadlines, scholarships", questions: ["When is the semester fee due?", "What scholarships are available?"] },
      { category: "examinations", title: "Exam cell", desc: "Timetables, revaluation, results", questions: ["When are the odd semester exams?", "How do I apply for revaluation?"] },
      { category: "placements", title: "Placement cell", desc: "Drives and registration", questions: ["When is the next placement drive?", "How do I register for placements?"] },
      { category: "hostel", title: "Hostel & campus", desc: "Hostel fees, facilities", questions: ["What's the hostel fee?", "How are hostel fees paid?"] },
      { category: "notices", title: "Notice board", desc: "Holidays and announcements", questions: ["Is the college closed this week?", "What are the latest announcements?"] },
    ],
  },
  hi: {
    tagline: "कॉलेज हेल्प डेस्क",
    offices: "कार्यालय",
    allOffices: "सभी कार्यालय",
    allOfficesDesc: "सभी दस्तावेज़ों में खोजें",
    admin: "एडमिन",
    welcomeTitle: "आज मैं आपकी क्या मदद करूं?",
    welcome:
      "प्रवेश, फीस, परीक्षा, प्लेसमेंट, हॉस्टल या सूचनाओं के बारे में पूछें। हर उत्तर आधिकारिक कॉलेज दस्तावेज़ से आता है, और उसका स्रोत नीचे दिखाया जाता है।",
    tryAsking: "ये पूछकर देखें",
    generalQuestions: ["प्रवेश के लिए कौन से दस्तावेज़ चाहिए?", "हॉस्टल फीस कितनी है?", "विषम सेमेस्टर की परीक्षाएं कब हैं?", "अगली प्लेसमेंट ड्राइव कब है?"],
    placeholder: "अपना प्रश्न लिखें…",
    send: "भेजें",
    newChat: "नई बातचीत",
    askingOffice: "पूछ रहे हैं:",
    thinking: "आधिकारिक दस्तावेज़ खोजे जा रहे हैं…",
    source: "स्रोत",
    confidence: "विश्वास स्तर",
    grounded: "आधिकारिक दस्तावेज़ से",
    notGrounded: "कोई मिलान दस्तावेज़ नहीं",
    backendOffline: "कॉलेजकनेक्ट सर्वर तक नहीं पहुंच सका। कृपया थोड़ी देर बाद पुनः प्रयास करें।",
    disclaimer: "उत्तर आधिकारिक कॉलेज दस्तावेज़ों से आते हैं। महत्वपूर्ण समय-सीमाओं के लिए उद्धृत स्रोत देखें।",
    officesList: [
      { category: "admissions", title: "प्रवेश", desc: "पात्रता, दस्तावेज़, समय-सीमा", questions: ["प्रवेश के लिए कौन से दस्तावेज़ चाहिए?", "आवेदन की अंतिम तिथि क्या है?"] },
      { category: "fees", title: "लेखा एवं फीस", desc: "फीस की तिथियां, छात्रवृत्ति", questions: ["सेमेस्टर फीस कब तक भरनी है?", "कौन सी छात्रवृत्तियां उपलब्ध हैं?"] },
      { category: "examinations", title: "परीक्षा प्रकोष्ठ", desc: "समय-सारणी, पुनर्मूल्यांकन, परिणाम", questions: ["विषम सेमेस्टर की परीक्षाएं कब हैं?", "पुनर्मूल्यांकन के लिए आवेदन कैसे करें?"] },
      { category: "placements", title: "प्लेसमेंट सेल", desc: "ड्राइव और पंजीकरण", questions: ["अगली प्लेसमेंट ड्राइव कब है?", "प्लेसमेंट के लिए पंजीकरण कैसे करें?"] },
      { category: "hostel", title: "हॉस्टल और कैंपस", desc: "हॉस्टल फीस, सुविधाएं", questions: ["हॉस्टल फीस कितनी है?", "हॉस्टल फीस कैसे भरी जाती है?"] },
      { category: "notices", title: "सूचना बोर्ड", desc: "छुट्टियां और घोषणाएं", questions: ["क्या इस हफ्ते कॉलेज बंद है?", "नवीनतम घोषणाएं क्या हैं?"] },
    ],
  },
  mr: {
    tagline: "कॉलेज हेल्प डेस्क",
    offices: "कार्यालये",
    allOffices: "सर्व कार्यालये",
    allOfficesDesc: "सर्व कागदपत्रांत शोधा",
    admin: "अ‍ॅडमिन",
    welcomeTitle: "आज मी तुम्हाला कशी मदत करू?",
    welcome:
      "प्रवेश, फी, परीक्षा, प्लेसमेंट, वसतिगृह किंवा सूचनांबद्दल विचारा. प्रत्येक उत्तर अधिकृत कॉलेज कागदपत्रातून येते, आणि त्याचा स्रोत खाली दाखवला जातो.",
    tryAsking: "हे विचारून पहा",
    generalQuestions: ["प्रवेशासाठी कोणती कागदपत्रे लागतात?", "वसतिगृह फी किती आहे?", "विषम सत्राच्या परीक्षा कधी आहेत?", "पुढील प्लेसमेंट ड्राइव्ह कधी आहे?"],
    placeholder: "तुमचा प्रश्न लिहा…",
    send: "पाठवा",
    newChat: "नवीन संभाषण",
    askingOffice: "विचारत आहात:",
    thinking: "अधिकृत दस्तऐवज शोधले जात आहेत…",
    source: "स्रोत",
    confidence: "विश्वासार्हता",
    grounded: "अधिकृत दस्तऐवजातून",
    notGrounded: "जुळणारा दस्तऐवज नाही",
    backendOffline: "कॉलेजकनेक्ट सर्व्हरशी संपर्क होऊ शकला नाही. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.",
    disclaimer: "उत्तरे अधिकृत कॉलेज कागदपत्रांतून येतात. महत्त्वाच्या मुदतींसाठी उद्धृत स्रोत तपासा.",
    officesList: [
      { category: "admissions", title: "प्रवेश", desc: "पात्रता, कागदपत्रे, मुदत", questions: ["प्रवेशासाठी कोणती कागदपत्रे लागतात?", "अर्जाची शेवटची तारीख कोणती?"] },
      { category: "fees", title: "लेखा व फी", desc: "फी मुदत, शिष्यवृत्ती", questions: ["सत्र फी कधीपर्यंत भरायची?", "कोणत्या शिष्यवृत्ती उपलब्ध आहेत?"] },
      { category: "examinations", title: "परीक्षा कक्ष", desc: "वेळापत्रक, पुनर्मूल्यांकन, निकाल", questions: ["विषम सत्राच्या परीक्षा कधी आहेत?", "पुनर्मूल्यांकनासाठी अर्ज कसा करावा?"] },
      { category: "placements", title: "प्लेसमेंट सेल", desc: "ड्राइव्ह आणि नोंदणी", questions: ["पुढील प्लेसमेंट ड्राइव्ह कधी आहे?", "प्लेसमेंटसाठी नोंदणी कशी करावी?"] },
      { category: "hostel", title: "वसतिगृह व कॅम्पस", desc: "वसतिगृह फी, सुविधा", questions: ["वसतिगृह फी किती आहे?", "वसतिगृह फी कशी भरायची?"] },
      { category: "notices", title: "सूचना फलक", desc: "सुट्ट्या आणि घोषणा", questions: ["या आठवड्यात कॉलेज बंद आहे का?", "नवीनतम घोषणा कोणत्या आहेत?"] },
    ],
  },
};
