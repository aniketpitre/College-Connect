import type { Language } from "./types";

export const UI_STRINGS: Record<Language, Record<string, string>> = {
  en: {
    appName: "CollegeConnect AI",
    tagline: "Your digital college help desk",
    inputPlaceholder: "Ask about admissions, fees, exams, placements...",
    send: "Send",
    welcome:
      "Hi! I'm CollegeConnect AI. Ask me anything about admissions, fees, exams, placements, hostel, or notices — I'll answer from official college documents and show you the source.",
    source: "Source",
    confidence: "Confidence",
    grounded: "Grounded in official document",
    notGrounded: "No matching document found",
    demoNotice:
      "Answers are generated from official college documents. Always check the cited source for important deadlines.",
    backendOffline:
      "Could not reach the CollegeConnect backend. Please make sure the API server is running.",
    categoriesLabel: "Quick topics",
    thinking: "Searching official documents...",
  },
  hi: {
    appName: "कॉलेजकनेक्ट AI",
    tagline: "आपका डिजिटल कॉलेज हेल्प डेस्क",
    inputPlaceholder: "प्रवेश, शुल्क, परीक्षा, प्लेसमेंट के बारे में पूछें...",
    send: "भेजें",
    welcome:
      "नमस्ते! मैं कॉलेजकनेक्ट AI हूं। प्रवेश, शुल्क, परीक्षा, प्लेसमेंट, छात्रावास या सूचनाओं के बारे में कुछ भी पूछें — मैं आधिकारिक कॉलेज दस्तावेज़ों से उत्तर दूंगा और स्रोत दिखाऊंगा।",
    source: "स्रोत",
    confidence: "विश्वास स्तर",
    grounded: "आधिकारिक दस्तावेज़ पर आधारित",
    notGrounded: "कोई मिलान दस्तावेज़ नहीं मिला",
    demoNotice:
      "उत्तर आधिकारिक कॉलेज दस्तावेज़ों से तैयार किए जाते हैं। महत्वपूर्ण समय-सीमाओं के लिए हमेशा उद्धृत स्रोत देखें।",
    backendOffline:
      "कॉलेजकनेक्ट बैकएंड तक नहीं पहुंच सका। कृपया सुनिश्चित करें कि API सर्वर चल रहा है।",
    categoriesLabel: "त्वरित विषय",
    thinking: "आधिकारिक दस्तावेज़ खोजे जा रहे हैं...",
  },
  mr: {
    appName: "कॉलेजकनेक्ट AI",
    tagline: "तुमचे डिजिटल कॉलेज हेल्प डेस्क",
    inputPlaceholder: "प्रवेश, शुल्क, परीक्षा, प्लेसमेंटबद्दल विचारा...",
    send: "पाठवा",
    welcome:
      "नमस्कार! मी कॉलेजकनेक्ट AI आहे. प्रवेश, शुल्क, परीक्षा, प्लेसमेंट, वसतिगृह किंवा सूचनांबद्दल काहीही विचारा — मी अधिकृत महाविद्यालयीन दस्तऐवजांमधून उत्तर देईन आणि स्रोत दाखवेन.",
    source: "स्रोत",
    confidence: "विश्वासार्हता",
    grounded: "अधिकृत दस्तऐवजावर आधारित",
    notGrounded: "जुळणारा दस्तऐवज सापडला नाही",
    demoNotice:
      "उत्तरे अधिकृत महाविद्यालयीन दस्तऐवजांमधून तयार केली जातात. महत्त्वाच्या मुदतींसाठी नेहमी उद्धृत स्रोत तपासा.",
    backendOffline:
      "कॉलेजकनेक्ट बॅकएंडशी संपर्क होऊ शकला नाही. कृपया API सर्व्हर सुरू असल्याची खात्री करा.",
    categoriesLabel: "जलद विषय",
    thinking: "अधिकृत दस्तऐवज शोधले जात आहेत...",
  },
};
