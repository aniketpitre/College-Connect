import type { Language } from "../lib/types";

/** 2-step verification, password reset and "My account" (students use these too). */
export interface AccountStrings {
  // 2-step verification
  twoStepTitle: string;
  verifyIntro: string;
  codeLabel: string;
  recoveryLabel: string;
  recoveryVerifyIntro: string;
  useRecovery: string;
  useApp: string;
  verify: string;
  verifying: string;
  setupIntroRequired: string;
  setupIntro: string;
  setupStep1: string;
  setupStep2: string;
  cantScan: string;
  setupStep3: string;
  turnOn: string;
  turningOn: string;
  recoveryTitle: string;
  recoveryIntro: string;
  copyCodes: string;
  copied: string;
  savedContinue: string;
  cancelSignIn: string;
  // forgot / reset password
  forgotTitle: string;
  forgotIntro: string;
  identifier: string;
  sendLink: string;
  sending: string;
  forgotDone: string;
  noEmailHint: string;
  backToSignIn: string;
  resetTitle: string;
  resetDone: string;
  requestNew: string;
  // my account
  accountTitle: string;
  passwordSection: string;
  passwordHelp: string;
  changePassword: string;
  on: string;
  off: string;
  requiredForRole: string;
  twoStepOffHelp: string;
  setUp: string;
  turnOff: string;
  recoveryLeft: (n: number) => string;
  newCodes: string;
  passwordToConfirm: string;
  confirm: string;
  cancel: string;
  devicesSection: string;
  thisDevice: string;
  unknownDevice: string;
  lastActive: string;
  signOutDevice: string;
  signOutEverywhere: string;
  activitySection: string;
  noActivity: string;
  actions: Record<string, string>;
}

export const ACCOUNT_STRINGS: Record<Language, AccountStrings> = {
  en: {
    twoStepTitle: "2-step verification",
    verifyIntro: "Open your authenticator app and enter the 6-digit code for CollegeConnect.",
    codeLabel: "6-digit code",
    recoveryLabel: "Recovery code",
    recoveryVerifyIntro: "Enter one of the recovery codes you saved when you set up 2-step verification.",
    useRecovery: "Lost your phone? Use a recovery code",
    useApp: "Use the authenticator app instead",
    verify: "Verify",
    verifying: "Checking…",
    setupIntroRequired: "Your role needs 2-step verification. Setting it up takes about a minute.",
    setupIntro: "Add a second step to your sign-in: a code from an app on your phone.",
    setupStep1: "Install an authenticator app on your phone (Google Authenticator, Microsoft Authenticator or similar).",
    setupStep2: "In the app, add an account and scan this QR code.",
    cantScan: "Can't scan? Type this key instead:",
    setupStep3: "Enter the 6-digit code the app shows.",
    turnOn: "Turn on 2-step verification",
    turningOn: "Turning on…",
    recoveryTitle: "Save your recovery codes",
    recoveryIntro:
      "If you lose your phone, each code lets you sign in once. Write them down or save them somewhere safe; they won't be shown again.",
    copyCodes: "Copy codes",
    copied: "Copied",
    savedContinue: "I've saved them, continue",
    cancelSignIn: "Cancel and sign out",
    forgotTitle: "Reset your password",
    forgotIntro: "Enter your college email or PRN. If your account has an email address, we'll send you a reset link.",
    identifier: "College email or PRN",
    sendLink: "Send reset link",
    sending: "Sending…",
    forgotDone: "If an account with an email address matches, a reset link is on its way. It works for 30 minutes.",
    noEmailHint: "No email address on your account? Ask the college office for a temporary password.",
    backToSignIn: "Back to sign in",
    resetTitle: "Choose a new password",
    resetDone: "Your password has been changed and other devices were signed out. You can sign in now.",
    requestNew: "Ask for a new link",
    accountTitle: "My account",
    passwordSection: "Password",
    passwordHelp: "Changing your password signs out your other devices.",
    changePassword: "Change password",
    on: "On",
    off: "Off",
    requiredForRole: "Required for your role",
    twoStepOffHelp: "Protect your account with a code from your phone as well as your password.",
    setUp: "Set up",
    turnOff: "Turn off",
    recoveryLeft: (n) => (n === 1 ? "1 recovery code left" : `${n} recovery codes left`),
    newCodes: "Get new recovery codes",
    passwordToConfirm: "Enter your password to confirm",
    confirm: "Confirm",
    cancel: "Cancel",
    devicesSection: "Signed-in devices",
    thisDevice: "This device",
    unknownDevice: "Unknown device",
    lastActive: "Last active",
    signOutDevice: "Sign out",
    signOutEverywhere: "Sign out everywhere",
    activitySection: "Recent sign-in activity",
    noActivity: "No activity yet.",
    actions: {
      "auth.login.succeeded": "Signed in",
      "auth.login.failed": "Failed sign-in attempt",
      "auth.logout": "Signed out",
      "auth.logout_all": "Signed out everywhere",
      "auth.session.ended": "A device was signed out",
      "auth.account.locked": "Account locked after wrong passwords",
      "auth.password.changed": "Password changed",
      "auth.password.reset_requested": "Password reset requested",
      "auth.password.reset_completed": "Password reset",
      "auth.mfa.enabled": "2-step verification turned on",
      "auth.mfa.disabled": "2-step verification turned off",
      "auth.mfa.verified": "2-step code accepted",
      "auth.mfa.failed": "Wrong 2-step code",
      "auth.mfa.recovery_codes_replaced": "New recovery codes created",
    },
  },
  hi: {
    twoStepTitle: "2-चरण सत्यापन",
    verifyIntro: "अपना ऑथेंटिकेटर ऐप खोलें और कॉलेजकनेक्ट का 6-अंकों का कोड दर्ज करें।",
    codeLabel: "6-अंकों का कोड",
    recoveryLabel: "रिकवरी कोड",
    recoveryVerifyIntro: "2-चरण सत्यापन सेट करते समय सहेजे गए रिकवरी कोड में से एक दर्ज करें।",
    useRecovery: "फ़ोन खो गया? रिकवरी कोड का उपयोग करें",
    useApp: "इसके बजाय ऑथेंटिकेटर ऐप का उपयोग करें",
    verify: "सत्यापित करें",
    verifying: "जांच हो रही है…",
    setupIntroRequired: "आपकी भूमिका के लिए 2-चरण सत्यापन ज़रूरी है। इसे सेट करने में लगभग एक मिनट लगता है।",
    setupIntro: "साइन इन में एक दूसरा चरण जोड़ें: आपके फ़ोन के ऐप से एक कोड।",
    setupStep1: "अपने फ़ोन पर एक ऑथेंटिकेटर ऐप इंस्टॉल करें (Google Authenticator, Microsoft Authenticator या ऐसा कोई ऐप)।",
    setupStep2: "ऐप में एक खाता जोड़ें और यह QR कोड स्कैन करें।",
    cantScan: "स्कैन नहीं हो रहा? इसके बजाय यह कुंजी लिखें:",
    setupStep3: "ऐप में दिख रहा 6-अंकों का कोड दर्ज करें।",
    turnOn: "2-चरण सत्यापन चालू करें",
    turningOn: "चालू हो रहा है…",
    recoveryTitle: "अपने रिकवरी कोड सहेजें",
    recoveryIntro:
      "फ़ोन खो जाने पर, हर कोड से आप एक बार साइन इन कर सकते हैं। इन्हें लिख लें या किसी सुरक्षित जगह सहेजें; ये दोबारा नहीं दिखाए जाएंगे।",
    copyCodes: "कोड कॉपी करें",
    copied: "कॉपी हो गया",
    savedContinue: "मैंने सहेज लिए, आगे बढ़ें",
    cancelSignIn: "रद्द करें और साइन आउट करें",
    forgotTitle: "अपना पासवर्ड रीसेट करें",
    forgotIntro: "अपना कॉलेज ईमेल या PRN दर्ज करें। अगर आपके खाते में ईमेल पता है, तो हम रीसेट लिंक भेजेंगे।",
    identifier: "कॉलेज ईमेल या PRN",
    sendLink: "रीसेट लिंक भेजें",
    sending: "भेजा जा रहा है…",
    forgotDone: "अगर ईमेल पते वाला कोई खाता मेल खाता है, तो रीसेट लिंक भेजा जा रहा है। यह 30 मिनट तक काम करेगा।",
    noEmailHint: "आपके खाते में ईमेल पता नहीं है? कॉलेज कार्यालय से अस्थायी पासवर्ड मांगें।",
    backToSignIn: "साइन इन पर वापस जाएं",
    resetTitle: "नया पासवर्ड चुनें",
    resetDone: "आपका पासवर्ड बदल गया है और अन्य डिवाइस साइन आउट हो गए हैं। अब आप साइन इन कर सकते हैं।",
    requestNew: "नया लिंक मांगें",
    accountTitle: "मेरा खाता",
    passwordSection: "पासवर्ड",
    passwordHelp: "पासवर्ड बदलने पर आपके अन्य डिवाइस साइन आउट हो जाते हैं।",
    changePassword: "पासवर्ड बदलें",
    on: "चालू",
    off: "बंद",
    requiredForRole: "आपकी भूमिका के लिए ज़रूरी",
    twoStepOffHelp: "पासवर्ड के साथ अपने फ़ोन के कोड से अपने खाते को सुरक्षित रखें।",
    setUp: "सेट करें",
    turnOff: "बंद करें",
    recoveryLeft: (n) => `${n} रिकवरी कोड बाकी`,
    newCodes: "नए रिकवरी कोड पाएं",
    passwordToConfirm: "पुष्टि के लिए अपना पासवर्ड दर्ज करें",
    confirm: "पुष्टि करें",
    cancel: "रद्द करें",
    devicesSection: "साइन-इन डिवाइस",
    thisDevice: "यह डिवाइस",
    unknownDevice: "अज्ञात डिवाइस",
    lastActive: "आखिरी बार सक्रिय",
    signOutDevice: "साइन आउट",
    signOutEverywhere: "हर जगह से साइन आउट करें",
    activitySection: "हाल की साइन-इन गतिविधि",
    noActivity: "अभी कोई गतिविधि नहीं।",
    actions: {
      "auth.login.succeeded": "साइन इन किया",
      "auth.login.failed": "साइन इन का असफल प्रयास",
      "auth.logout": "साइन आउट किया",
      "auth.logout_all": "हर जगह से साइन आउट किया",
      "auth.session.ended": "एक डिवाइस साइन आउट किया गया",
      "auth.account.locked": "गलत पासवर्ड के बाद खाता लॉक हुआ",
      "auth.password.changed": "पासवर्ड बदला गया",
      "auth.password.reset_requested": "पासवर्ड रीसेट का अनुरोध",
      "auth.password.reset_completed": "पासवर्ड रीसेट हुआ",
      "auth.mfa.enabled": "2-चरण सत्यापन चालू हुआ",
      "auth.mfa.disabled": "2-चरण सत्यापन बंद हुआ",
      "auth.mfa.verified": "2-चरण कोड स्वीकार हुआ",
      "auth.mfa.failed": "गलत 2-चरण कोड",
      "auth.mfa.recovery_codes_replaced": "नए रिकवरी कोड बनाए गए",
    },
  },
  mr: {
    twoStepTitle: "2-टप्पी पडताळणी",
    verifyIntro: "तुमचे ऑथेंटिकेटर ॲप उघडा आणि कॉलेजकनेक्टचा 6-अंकी कोड टाका.",
    codeLabel: "6-अंकी कोड",
    recoveryLabel: "रिकव्हरी कोड",
    recoveryVerifyIntro: "2-टप्पी पडताळणी सेट करताना जतन केलेल्या रिकव्हरी कोडपैकी एक टाका.",
    useRecovery: "फोन हरवला? रिकव्हरी कोड वापरा",
    useApp: "त्याऐवजी ऑथेंटिकेटर ॲप वापरा",
    verify: "पडताळा",
    verifying: "तपासत आहे…",
    setupIntroRequired: "तुमच्या भूमिकेसाठी 2-टप्पी पडताळणी आवश्यक आहे. ती सेट करायला सुमारे एक मिनिट लागतो.",
    setupIntro: "साइन इनमध्ये दुसरा टप्पा जोडा: तुमच्या फोनवरील ॲपमधून एक कोड.",
    setupStep1: "तुमच्या फोनवर ऑथेंटिकेटर ॲप इंस्टॉल करा (Google Authenticator, Microsoft Authenticator किंवा तत्सम).",
    setupStep2: "ॲपमध्ये खाते जोडा आणि हा QR कोड स्कॅन करा.",
    cantScan: "स्कॅन होत नाही? त्याऐवजी ही की टाइप करा:",
    setupStep3: "ॲपमध्ये दिसणारा 6-अंकी कोड टाका.",
    turnOn: "2-टप्पी पडताळणी सुरू करा",
    turningOn: "सुरू होत आहे…",
    recoveryTitle: "तुमचे रिकव्हरी कोड जतन करा",
    recoveryIntro:
      "फोन हरवल्यास, प्रत्येक कोडने तुम्ही एकदा साइन इन करू शकता. ते लिहून ठेवा किंवा सुरक्षित ठिकाणी जतन करा; ते पुन्हा दाखवले जाणार नाहीत.",
    copyCodes: "कोड कॉपी करा",
    copied: "कॉपी झाले",
    savedContinue: "मी जतन केले, पुढे जा",
    cancelSignIn: "रद्द करा आणि साइन आउट करा",
    forgotTitle: "तुमचा पासवर्ड रीसेट करा",
    forgotIntro: "तुमचा कॉलेज ईमेल किंवा PRN टाका. तुमच्या खात्यावर ईमेल पत्ता असल्यास, आम्ही रीसेट लिंक पाठवू.",
    identifier: "कॉलेज ईमेल किंवा PRN",
    sendLink: "रीसेट लिंक पाठवा",
    sending: "पाठवत आहे…",
    forgotDone: "ईमेल पत्ता असलेले खाते जुळल्यास, रीसेट लिंक पाठवली जात आहे. ती 30 मिनिटे चालेल.",
    noEmailHint: "तुमच्या खात्यावर ईमेल पत्ता नाही? कॉलेज कार्यालयाकडून तात्पुरता पासवर्ड मागा.",
    backToSignIn: "साइन इनवर परत जा",
    resetTitle: "नवीन पासवर्ड निवडा",
    resetDone: "तुमचा पासवर्ड बदलला आहे आणि इतर डिव्हाइस साइन आउट झाले आहेत. आता तुम्ही साइन इन करू शकता.",
    requestNew: "नवीन लिंक मागा",
    accountTitle: "माझे खाते",
    passwordSection: "पासवर्ड",
    passwordHelp: "पासवर्ड बदलल्यावर तुमची इतर डिव्हाइस साइन आउट होतात.",
    changePassword: "पासवर्ड बदला",
    on: "सुरू",
    off: "बंद",
    requiredForRole: "तुमच्या भूमिकेसाठी आवश्यक",
    twoStepOffHelp: "पासवर्डसोबत तुमच्या फोनवरील कोडने तुमचे खाते सुरक्षित ठेवा.",
    setUp: "सेट करा",
    turnOff: "बंद करा",
    recoveryLeft: (n) => `${n} रिकव्हरी कोड शिल्लक`,
    newCodes: "नवीन रिकव्हरी कोड मिळवा",
    passwordToConfirm: "खात्री करण्यासाठी तुमचा पासवर्ड टाका",
    confirm: "खात्री करा",
    cancel: "रद्द करा",
    devicesSection: "साइन-इन केलेली डिव्हाइस",
    thisDevice: "हे डिव्हाइस",
    unknownDevice: "अज्ञात डिव्हाइस",
    lastActive: "शेवटचे सक्रिय",
    signOutDevice: "साइन आउट",
    signOutEverywhere: "सर्व ठिकाणांहून साइन आउट करा",
    activitySection: "अलीकडील साइन-इन घडामोडी",
    noActivity: "अजून कोणतीही घडामोड नाही.",
    actions: {
      "auth.login.succeeded": "साइन इन केले",
      "auth.login.failed": "साइन इनचा अयशस्वी प्रयत्न",
      "auth.logout": "साइन आउट केले",
      "auth.logout_all": "सर्व ठिकाणांहून साइन आउट केले",
      "auth.session.ended": "एक डिव्हाइस साइन आउट केले",
      "auth.account.locked": "चुकीच्या पासवर्डनंतर खाते लॉक झाले",
      "auth.password.changed": "पासवर्ड बदलला",
      "auth.password.reset_requested": "पासवर्ड रीसेटची विनंती",
      "auth.password.reset_completed": "पासवर्ड रीसेट झाला",
      "auth.mfa.enabled": "2-टप्पी पडताळणी सुरू झाली",
      "auth.mfa.disabled": "2-टप्पी पडताळणी बंद झाली",
      "auth.mfa.verified": "2-टप्पी कोड स्वीकारला",
      "auth.mfa.failed": "चुकीचा 2-टप्पी कोड",
      "auth.mfa.recovery_codes_replaced": "नवीन रिकव्हरी कोड तयार केले",
    },
  },
};
