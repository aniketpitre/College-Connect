import type { Language } from "../lib/types";

export interface AuthStrings {
  signIn: string;
  signInTitle: string;
  student: string;
  staff: string;
  prn: string;
  prnHint: string;
  email: string;
  password: string;
  show: string;
  hide: string;
  signingIn: string;
  forgot: string;
  backToHome: string;
  errors: Record<string, string>;
  changeTitle: string;
  changeIntroForced: string;
  changeIntro: string;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
  passwordRules: string;
  mismatch: string;
  save: string;
  saving: string;
  signOut: string;
}

export const AUTH_STRINGS: Record<Language, AuthStrings> = {
  en: {
    signIn: "Sign in",
    signInTitle: "Sign in to CollegeConnect",
    student: "Student",
    staff: "Staff",
    prn: "PRN",
    prnHint: "As printed on your admission slip, e.g. 2026BCA001",
    email: "College email",
    password: "Password",
    show: "Show",
    hide: "Hide",
    signingIn: "Signing in…",
    forgot: "Forgot password?",
    backToHome: "Back to the home page",
    errors: {
      invalid_credentials: "Wrong PRN/email or password.",
      account_locked: "Too many wrong attempts. Please try again in 15 minutes.",
      account_disabled: "This account is disabled. Please contact the college office.",
      rate_limited: "Too many attempts. Please wait a few minutes and try again.",
      network_error: "Could not reach the server. Check your connection and try again.",
      weak_password: "Choose a stronger password.",
      invalid_code: "That code is not correct. Check the time on your phone and try again.",
      invalid_token: "This reset link is invalid or has expired. Ask for a new one.",
    },
    changeTitle: "Set a new password",
    changeIntroForced: "For your security, choose your own password before continuing.",
    changeIntro: "Choose a new password. Other devices will be signed out.",
    currentPassword: "Current (or temporary) password",
    newPassword: "New password",
    confirmPassword: "Type the new password again",
    passwordRules: "At least 10 characters. Avoid your name, PRN and common passwords. A short sentence works well.",
    mismatch: "The two passwords don't match.",
    save: "Save password",
    saving: "Saving…",
    signOut: "Sign out",
  },
  hi: {
    signIn: "साइन इन",
    signInTitle: "कॉलेजकनेक्ट में साइन इन करें",
    student: "छात्र",
    staff: "स्टाफ",
    prn: "PRN",
    prnHint: "जैसा प्रवेश पर्ची पर छपा है, जैसे 2026BCA001",
    email: "कॉलेज ईमेल",
    password: "पासवर्ड",
    show: "दिखाएं",
    hide: "छिपाएं",
    signingIn: "साइन इन हो रहा है…",
    forgot: "पासवर्ड भूल गए?",
    backToHome: "मुख्य पृष्ठ पर वापस जाएं",
    errors: {
      invalid_credentials: "PRN/ईमेल या पासवर्ड गलत है।",
      account_locked: "बहुत अधिक गलत प्रयास। कृपया 15 मिनट बाद फिर कोशिश करें।",
      account_disabled: "यह खाता बंद है। कृपया कॉलेज कार्यालय से संपर्क करें।",
      rate_limited: "बहुत अधिक प्रयास। कृपया कुछ मिनट रुककर फिर कोशिश करें।",
      network_error: "सर्वर तक नहीं पहुंच सके। अपना कनेक्शन जांचें और फिर कोशिश करें।",
      weak_password: "अधिक मजबूत पासवर्ड चुनें।",
      invalid_code: "यह कोड सही नहीं है। अपने फ़ोन का समय जांचें और फिर कोशिश करें।",
      invalid_token: "यह रीसेट लिंक अमान्य है या इसकी समय-सीमा खत्म हो गई है। नया लिंक मांगें।",
    },
    changeTitle: "नया पासवर्ड सेट करें",
    changeIntroForced: "आपकी सुरक्षा के लिए, आगे बढ़ने से पहले अपना पासवर्ड चुनें।",
    changeIntro: "नया पासवर्ड चुनें। अन्य डिवाइस साइन आउट हो जाएंगे।",
    currentPassword: "वर्तमान (या अस्थायी) पासवर्ड",
    newPassword: "नया पासवर्ड",
    confirmPassword: "नया पासवर्ड दोबारा लिखें",
    passwordRules: "कम से कम 10 अक्षर। अपना नाम, PRN और आम पासवर्ड न रखें। एक छोटा वाक्य अच्छा रहता है।",
    mismatch: "दोनों पासवर्ड मेल नहीं खाते।",
    save: "पासवर्ड सहेजें",
    saving: "सहेजा जा रहा है…",
    signOut: "साइन आउट",
  },
  mr: {
    signIn: "साइन इन",
    signInTitle: "कॉलेजकनेक्टमध्ये साइन इन करा",
    student: "विद्यार्थी",
    staff: "कर्मचारी",
    prn: "PRN",
    prnHint: "प्रवेश पावतीवर छापल्याप्रमाणे, उदा. 2026BCA001",
    email: "कॉलेज ईमेल",
    password: "पासवर्ड",
    show: "दाखवा",
    hide: "लपवा",
    signingIn: "साइन इन होत आहे…",
    forgot: "पासवर्ड विसरलात?",
    backToHome: "मुख्य पानावर परत जा",
    errors: {
      invalid_credentials: "PRN/ईमेल किंवा पासवर्ड चुकीचा आहे.",
      account_locked: "खूप चुकीचे प्रयत्न. कृपया 15 मिनिटांनी पुन्हा प्रयत्न करा.",
      account_disabled: "हे खाते बंद आहे. कृपया कॉलेज कार्यालयाशी संपर्क साधा.",
      rate_limited: "खूप प्रयत्न झाले. कृपया काही मिनिटे थांबून पुन्हा प्रयत्न करा.",
      network_error: "सर्व्हरशी संपर्क होऊ शकला नाही. तुमचे कनेक्शन तपासा आणि पुन्हा प्रयत्न करा.",
      weak_password: "अधिक मजबूत पासवर्ड निवडा.",
      invalid_code: "हा कोड बरोबर नाही. तुमच्या फोनवरील वेळ तपासा आणि पुन्हा प्रयत्न करा.",
      invalid_token: "ही रीसेट लिंक अवैध आहे किंवा तिची मुदत संपली आहे. नवीन लिंक मागा.",
    },
    changeTitle: "नवीन पासवर्ड सेट करा",
    changeIntroForced: "तुमच्या सुरक्षेसाठी, पुढे जाण्यापूर्वी स्वतःचा पासवर्ड निवडा.",
    changeIntro: "नवीन पासवर्ड निवडा. इतर डिव्हाइस साइन आउट होतील.",
    currentPassword: "सध्याचा (किंवा तात्पुरता) पासवर्ड",
    newPassword: "नवीन पासवर्ड",
    confirmPassword: "नवीन पासवर्ड पुन्हा लिहा",
    passwordRules: "किमान 10 अक्षरे. तुमचे नाव, PRN आणि सामान्य पासवर्ड टाळा. एक छोटे वाक्य चांगले काम करते.",
    mismatch: "दोन्ही पासवर्ड जुळत नाहीत.",
    save: "पासवर्ड जतन करा",
    saving: "जतन होत आहे…",
    signOut: "साइन आउट",
  },
};

/** Show a translated message for known error codes; fall back to the server's English message. */
export function errorText(t: AuthStrings, code: string | undefined, fallback: string): string {
  return (code && t.errors[code]) || fallback;
}
