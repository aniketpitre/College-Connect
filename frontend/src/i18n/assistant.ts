import type { Language } from "../lib/types";

export interface AssistantStrings {
  open: string;
  title: string;
  intro: string;
  placeholder: string;
  send: string;
  close: string;
  clear: string;
  thinking: string;
  source: string;
  notFound: string;
  error: string;
  disclaimer: string;
  examples: string[];
}

/** The assistant panel in every portal (students and parents see it in their language). */
export const ASSISTANT_STRINGS: Record<Language, AssistantStrings> = {
  en: {
    open: "Ask",
    title: "CollegeConnect AI",
    intro: "Ask about fees, exams, admissions, the hostel or any notice. Answers come only from the college's documents and notices, with the source.",
    placeholder: "Type your question…",
    send: "Ask",
    close: "Close",
    clear: "New chat",
    thinking: "Looking through the documents…",
    source: "Source",
    notFound: "Not found in the official documents",
    error: "The help desk can't be reached right now. Please try again.",
    disclaimer: "Check important dates with the office.",
    examples: ["When is the semester fee due?", "When are the exams?", "What scholarships are available?"],
  },
  hi: {
    open: "पूछें",
    title: "CollegeConnect AI",
    intro: "शुल्क, परीक्षा, प्रवेश, छात्रावास या किसी भी सूचना के बारे में पूछें। उत्तर केवल कॉलेज के दस्तावेज़ों और सूचनाओं से, स्रोत के साथ।",
    placeholder: "अपना प्रश्न लिखें…",
    send: "पूछें",
    close: "बंद करें",
    clear: "नई बातचीत",
    thinking: "दस्तावेज़ देखे जा रहे हैं…",
    source: "स्रोत",
    notFound: "आधिकारिक दस्तावेज़ों में नहीं मिला",
    error: "हेल्प डेस्क से अभी संपर्क नहीं हो पा रहा। कृपया फिर से प्रयास करें।",
    disclaimer: "महत्वपूर्ण तारीखें कार्यालय से पुष्टि करें।",
    examples: ["सेमेस्टर शुल्क कब तक भरना है?", "परीक्षाएँ कब हैं?", "कौन-सी छात्रवृत्तियाँ उपलब्ध हैं?"],
  },
  mr: {
    open: "विचारा",
    title: "CollegeConnect AI",
    intro: "शुल्क, परीक्षा, प्रवेश, वसतिगृह किंवा कोणत्याही सूचनेबद्दल विचारा. उत्तरे फक्त महाविद्यालयाच्या दस्तऐवज आणि सूचनांमधून, स्रोतासह.",
    placeholder: "तुमचा प्रश्न लिहा…",
    send: "विचारा",
    close: "बंद करा",
    clear: "नवीन संवाद",
    thinking: "दस्तऐवज पाहत आहे…",
    source: "स्रोत",
    notFound: "अधिकृत दस्तऐवजांमध्ये सापडले नाही",
    error: "हेल्प डेस्कशी सध्या संपर्क होत नाही. कृपया पुन्हा प्रयत्न करा.",
    disclaimer: "महत्त्वाच्या तारखा कार्यालयाकडून खात्री करून घ्या.",
    examples: ["सेमिस्टर शुल्क कधीपर्यंत भरायचे?", "परीक्षा कधी आहेत?", "कोणत्या शिष्यवृत्ती उपलब्ध आहेत?"],
  },
};
