import type { Language } from "../lib/types";

/** Attendance strings students see. */
export interface AttendanceStrings {
  title: string;
  overall: string;
  of: (attended: number, held: number) => string;
  minimum: (min: number) => string;
  canMiss: (n: number) => string;
  mustAttend: (n: number) => string;
  atMinimum: string;
  noLectures: string;
  recentDays: string;
  marks: { present: string; absent: string; exempt: string };
  exemptNote: string;
}

export const ATTENDANCE_STRINGS: Record<Language, AttendanceStrings> = {
  en: {
    title: "My attendance",
    overall: "Overall",
    of: (a, h) => `${a} of ${h} lectures`,
    minimum: (m) => `The minimum is ${m}% in every subject.`,
    canMiss: (n) => (n === 1 ? "You can miss 1 more lecture." : `You can miss ${n} more lectures.`),
    mustAttend: (n) => (n === 1 ? "Attend the next lecture to reach the minimum." : `Attend the next ${n} lectures in a row to reach the minimum.`),
    atMinimum: "You are exactly at the minimum: don't miss the next lecture.",
    noLectures: "No attendance has been marked yet this year.",
    recentDays: "Day by day",
    marks: { present: "Present", absent: "Absent", exempt: "Exempted" },
    exemptNote: "Medical leave or official duty? Submit the document at the college office; those days then count as attended.",
  },
  hi: {
    title: "मेरी उपस्थिति",
    overall: "कुल",
    of: (a, h) => `${h} में से ${a} लेक्चर`,
    minimum: (m) => `हर विषय में कम से कम ${m}% ज़रूरी है।`,
    canMiss: (n) => `आप ${n} और लेक्चर छोड़ सकते हैं।`,
    mustAttend: (n) => `न्यूनतम तक पहुँचने के लिए लगातार अगले ${n} लेक्चर में आएँ।`,
    atMinimum: "आप ठीक न्यूनतम पर हैं: अगला लेक्चर न छोड़ें।",
    noLectures: "इस वर्ष अभी तक कोई उपस्थिति दर्ज नहीं हुई है।",
    recentDays: "दिन-प्रतिदिन",
    marks: { present: "उपस्थित", absent: "अनुपस्थित", exempt: "छूट" },
    exemptNote: "मेडिकल छुट्टी या आधिकारिक ड्यूटी? कॉलेज ऑफ़िस में दस्तावेज़ जमा करें; वे दिन उपस्थित माने जाएँगे।",
  },
  mr: {
    title: "माझी हजेरी",
    overall: "एकूण",
    of: (a, h) => `${h} पैकी ${a} लेक्चर`,
    minimum: (m) => `प्रत्येक विषयात किमान ${m}% आवश्यक आहे.`,
    canMiss: (n) => `तुम्ही आणखी ${n} लेक्चर चुकवू शकता.`,
    mustAttend: (n) => `किमान गाठण्यासाठी पुढील ${n} लेक्चर सलग उपस्थित राहा.`,
    atMinimum: "तुम्ही अगदी किमान मर्यादेवर आहात: पुढचे लेक्चर चुकवू नका.",
    noLectures: "या वर्षी अजून हजेरी नोंदवलेली नाही.",
    recentDays: "दिवसानुसार",
    marks: { present: "उपस्थित", absent: "गैरहजर", exempt: "सवलत" },
    exemptNote: "वैद्यकीय रजा किंवा अधिकृत ड्युटी? कॉलेज ऑफिसमध्ये कागदपत्र जमा करा; ते दिवस उपस्थित धरले जातील.",
  },
};
