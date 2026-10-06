import type { Language } from "../lib/types";

/** Student pages for the library, hostel and placement, in English, Hindi and Marathi. */
export interface CampusStrings {
  library: {
    title: string;
    rules: (days: number, max: number, fine: string) => string;
    myBooks: string;
    none: string;
    due: (d: string) => string;
    late: (days: number, fine: string) => string;
    renew: string;
    reservations: string;
    position: (n: number) => string;
    ready: (d: string) => string;
    cancel: string;
    search: string;
    searchHint: string;
    available: (n: number, total: number) => string;
    reserve: string;
    history: string;
    fine: (amount: string) => string;
  };
  hostel: {
    title: string;
    notResident: string;
    room: (block: string, room: string, bed: number) => string;
    since: (d: string) => string;
    outpass: string;
    leaveAt: string;
    returnBy: string;
    destination: string;
    reason: string;
    ask: string;
    statuses: Record<string, string>;
    late: string;
    complaints: string;
    category: string;
    categories: Record<string, string>;
    describe: string;
    send: string;
    complaintStatus: Record<string, string>;
    mess: string;
    days: Record<string, string>;
  };
  placement: {
    title: string;
    standing: (cgpa: string, backlogs: number) => string;
    profile: string;
    skills: string;
    linkedin: string;
    save: string;
    resume: string;
    uploadResume: string;
    noResume: string;
    drives: string;
    noDrives: string;
    package: (lpa: number) => string;
    registerBy: (d: string) => string;
    eligible: string;
    notEligible: string;
    reasons: Record<string, string>;
    register: string;
    withdraw: string;
    stage: string;
    offer: (lpa: number) => string;
  };
}

export const CAMPUS_STRINGS: Record<Language, CampusStrings> = {
  en: {
    library: {
      title: "Library",
      rules: (d, m, f) => `Borrow up to ${m} books for ${d} days. A late book costs ${f} a day, added to your fees.`,
      myBooks: "My books",
      none: "You have no books right now.",
      due: (d) => `Due ${d}`,
      late: (n, f) => `${n} day(s) late · fine so far ${f}`,
      renew: "Renew",
      reservations: "My reservations",
      position: (n) => `Number ${n} in the queue`,
      ready: (d) => `Ready at the counter until ${d}`,
      cancel: "Cancel",
      search: "Find a book",
      searchHint: "Title, author or ISBN",
      available: (n, t) => `${n} of ${t} on the shelf`,
      reserve: "Reserve",
      history: "Returned",
      fine: (a) => `Fine ${a}`,
    },
    hostel: {
      title: "Hostel",
      notResident: "You don't have a hostel room. Ask the hostel warden.",
      room: (b, r, bed) => `${b}, room ${r}, bed ${bed}`,
      since: (d) => `Since ${d}`,
      outpass: "Out-pass",
      leaveAt: "Leaving",
      returnBy: "Back by",
      destination: "Going to",
      reason: "Reason",
      ask: "Ask for an out-pass",
      statuses: { requested: "Waiting for the warden", approved: "Approved", rejected: "Not approved", out: "Out", returned: "Returned", cancelled: "Cancelled" },
      late: "Returned late",
      complaints: "Complaints",
      category: "About",
      categories: { room: "Room", water: "Water", electricity: "Electricity", cleaning: "Cleaning", mess: "Mess", other: "Other" },
      describe: "What is the problem?",
      send: "Send",
      complaintStatus: { open: "Open", in_progress: "Being fixed", resolved: "Resolved" },
      mess: "Mess menu",
      days: { mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday" },
    },
    placement: {
      title: "Placement",
      standing: (c, b) => `Your CGPA ${c} · backlogs ${b}`,
      profile: "My placement profile",
      skills: "Skills",
      linkedin: "LinkedIn profile",
      save: "Save",
      resume: "Resume",
      uploadResume: "Upload resume (PDF)",
      noResume: "No resume yet: upload one to register for drives.",
      drives: "Placement drives",
      noDrives: "No drives open right now.",
      package: (l) => `₹${l} lakh a year`,
      registerBy: (d) => `Register by ${d}`,
      eligible: "You are eligible",
      notEligible: "Not eligible:",
      reasons: { programme: "programme", year: "year", cgpa: "CGPA", backlogs: "backlogs" },
      register: "Register",
      withdraw: "Withdraw",
      stage: "Stage",
      offer: (l) => `Selected! Offer ₹${l} lakh a year`,
    },
  },
  hi: {
    library: {
      title: "पुस्तकालय",
      rules: (d, m, f) => `${d} दिनों के लिए ${m} पुस्तकें तक लें। देरी पर प्रतिदिन ${f} जुर्माना, जो आपकी फ़ीस में जुड़ेगा।`,
      myBooks: "मेरी पुस्तकें",
      none: "अभी आपके पास कोई पुस्तक नहीं है।",
      due: (d) => `लौटाने की तिथि ${d}`,
      late: (n, f) => `${n} दिन की देरी · अब तक जुर्माना ${f}`,
      renew: "नवीनीकरण",
      reservations: "मेरे आरक्षण",
      position: (n) => `कतार में ${n}वाँ`,
      ready: (d) => `${d} तक काउंटर पर रखी है`,
      cancel: "रद्द करें",
      search: "पुस्तक खोजें",
      searchHint: "शीर्षक, लेखक या ISBN",
      available: (n, t) => `${t} में से ${n} उपलब्ध`,
      reserve: "आरक्षित करें",
      history: "लौटाई गई",
      fine: (a) => `जुर्माना ${a}`,
    },
    hostel: {
      title: "हॉस्टल",
      notResident: "आपके पास हॉस्टल कमरा नहीं है। हॉस्टल वार्डन से पूछें।",
      room: (b, r, bed) => `${b}, कमरा ${r}, बिस्तर ${bed}`,
      since: (d) => `${d} से`,
      outpass: "आउट-पास",
      leaveAt: "जाने का समय",
      returnBy: "लौटने का समय",
      destination: "कहाँ जा रहे हैं",
      reason: "कारण",
      ask: "आउट-पास माँगें",
      statuses: { requested: "वार्डन की प्रतीक्षा", approved: "स्वीकृत", rejected: "स्वीकृत नहीं", out: "बाहर", returned: "लौट आए", cancelled: "रद्द" },
      late: "देर से लौटे",
      complaints: "शिकायतें",
      category: "विषय",
      categories: { room: "कमरा", water: "पानी", electricity: "बिजली", cleaning: "सफ़ाई", mess: "मेस", other: "अन्य" },
      describe: "समस्या क्या है?",
      send: "भेजें",
      complaintStatus: { open: "खुली", in_progress: "ठीक हो रही है", resolved: "हल हुई" },
      mess: "मेस मेनू",
      days: { mon: "सोमवार", tue: "मंगलवार", wed: "बुधवार", thu: "गुरुवार", fri: "शुक्रवार", sat: "शनिवार", sun: "रविवार" },
    },
    placement: {
      title: "प्लेसमेंट",
      standing: (c, b) => `आपका CGPA ${c} · बैकलॉग ${b}`,
      profile: "मेरी प्लेसमेंट प्रोफ़ाइल",
      skills: "कौशल",
      linkedin: "LinkedIn प्रोफ़ाइल",
      save: "सहेजें",
      resume: "रिज़्यूमे",
      uploadResume: "रिज़्यूमे अपलोड करें (PDF)",
      noResume: "अभी रिज़्यूमे नहीं: ड्राइव में पंजीकरण के लिए अपलोड करें।",
      drives: "प्लेसमेंट ड्राइव",
      noDrives: "अभी कोई ड्राइव खुली नहीं है।",
      package: (l) => `₹${l} लाख प्रति वर्ष`,
      registerBy: (d) => `${d} तक पंजीकरण`,
      eligible: "आप पात्र हैं",
      notEligible: "पात्र नहीं:",
      reasons: { programme: "पाठ्यक्रम", year: "वर्ष", cgpa: "CGPA", backlogs: "बैकलॉग" },
      register: "पंजीकरण करें",
      withdraw: "नाम वापस लें",
      stage: "चरण",
      offer: (l) => `चयन हुआ! ऑफ़र ₹${l} लाख प्रति वर्ष`,
    },
  },
  mr: {
    library: {
      title: "ग्रंथालय",
      rules: (d, m, f) => `${d} दिवसांसाठी ${m} पुस्तके घ्या. उशिरा परत केल्यास दररोज ${f} दंड, तुमच्या शुल्कात जोडला जाईल.`,
      myBooks: "माझी पुस्तके",
      none: "सध्या तुमच्याकडे कोणतेही पुस्तक नाही.",
      due: (d) => `परत करण्याची तारीख ${d}`,
      late: (n, f) => `${n} दिवस उशीर · आतापर्यंत दंड ${f}`,
      renew: "नूतनीकरण",
      reservations: "माझी आरक्षणे",
      position: (n) => `रांगेत ${n} वा`,
      ready: (d) => `${d} पर्यंत काउंटरवर ठेवले आहे`,
      cancel: "रद्द करा",
      search: "पुस्तक शोधा",
      searchHint: "शीर्षक, लेखक किंवा ISBN",
      available: (n, t) => `${t} पैकी ${n} उपलब्ध`,
      reserve: "राखीव करा",
      history: "परत केलेली",
      fine: (a) => `दंड ${a}`,
    },
    hostel: {
      title: "वसतिगृह",
      notResident: "तुम्हाला वसतिगृहात खोली नाही. वसतिगृह वॉर्डनला विचारा.",
      room: (b, r, bed) => `${b}, खोली ${r}, बेड ${bed}`,
      since: (d) => `${d} पासून`,
      outpass: "आउट-पास",
      leaveAt: "जाण्याची वेळ",
      returnBy: "परत येण्याची वेळ",
      destination: "कुठे जात आहात",
      reason: "कारण",
      ask: "आउट-पास मागा",
      statuses: { requested: "वॉर्डनची प्रतीक्षा", approved: "मंजूर", rejected: "मंजूर नाही", out: "बाहेर", returned: "परत आले", cancelled: "रद्द" },
      late: "उशिरा परत आले",
      complaints: "तक्रारी",
      category: "विषय",
      categories: { room: "खोली", water: "पाणी", electricity: "वीज", cleaning: "स्वच्छता", mess: "मेस", other: "इतर" },
      describe: "काय अडचण आहे?",
      send: "पाठवा",
      complaintStatus: { open: "खुली", in_progress: "दुरुस्ती सुरू", resolved: "सोडवली" },
      mess: "मेस मेनू",
      days: { mon: "सोमवार", tue: "मंगळवार", wed: "बुधवार", thu: "गुरुवार", fri: "शुक्रवार", sat: "शनिवार", sun: "रविवार" },
    },
    placement: {
      title: "प्लेसमेंट",
      standing: (c, b) => `तुमचा CGPA ${c} · बॅकलॉग ${b}`,
      profile: "माझी प्लेसमेंट प्रोफाइल",
      skills: "कौशल्ये",
      linkedin: "LinkedIn प्रोफाइल",
      save: "जतन करा",
      resume: "रेझ्युमे",
      uploadResume: "रेझ्युमे अपलोड करा (PDF)",
      noResume: "अजून रेझ्युमे नाही: ड्राइव्हसाठी नोंदणी करण्यासाठी अपलोड करा.",
      drives: "प्लेसमेंट ड्राइव्ह",
      noDrives: "सध्या कोणताही ड्राइव्ह सुरू नाही.",
      package: (l) => `₹${l} लाख प्रति वर्ष`,
      registerBy: (d) => `${d} पर्यंत नोंदणी`,
      eligible: "तुम्ही पात्र आहात",
      notEligible: "पात्र नाही:",
      reasons: { programme: "अभ्यासक्रम", year: "वर्ष", cgpa: "CGPA", backlogs: "बॅकलॉग" },
      register: "नोंदणी करा",
      withdraw: "माघार घ्या",
      stage: "टप्पा",
      offer: (l) => `निवड झाली! ऑफर ₹${l} लाख प्रति वर्ष`,
    },
  },
};
