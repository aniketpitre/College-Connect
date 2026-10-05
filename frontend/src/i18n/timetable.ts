import type { Language } from "../lib/types";

/** Timetable strings students see (staff screens use English). */
export interface TimetableStrings {
  title: string;
  days: string[];
  thisWeek: string;
  prev: string;
  next: string;
  holiday: string;
  noLectures: string;
  cancelled: string;
  substitute: string;
  room: string;
  batch: string;
  noDivision: string;
}

export const TIMETABLE_STRINGS: Record<Language, TimetableStrings> = {
  en: {
    title: "My timetable",
    days: ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    thisWeek: "This week",
    prev: "← Previous week",
    next: "Next week →",
    holiday: "Holiday",
    noLectures: "No lectures",
    cancelled: "Cancelled",
    substitute: "Taken by",
    room: "Room",
    batch: "Batch",
    noDivision: "You haven't been placed in a division yet. Please contact the college office.",
  },
  hi: {
    title: "मेरी समय सारणी",
    days: ["", "सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार"],
    thisWeek: "यह सप्ताह",
    prev: "← पिछला सप्ताह",
    next: "अगला सप्ताह →",
    holiday: "छुट्टी",
    noLectures: "कोई लेक्चर नहीं",
    cancelled: "रद्द",
    substitute: "लेंगे:",
    room: "कमरा",
    batch: "बैच",
    noDivision: "आपको अभी तक किसी डिवीज़न में नहीं रखा गया है। कृपया कॉलेज ऑफ़िस से संपर्क करें।",
  },
  mr: {
    title: "माझे वेळापत्रक",
    days: ["", "सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार"],
    thisWeek: "हा आठवडा",
    prev: "← मागील आठवडा",
    next: "पुढील आठवडा →",
    holiday: "सुट्टी",
    noLectures: "लेक्चर नाहीत",
    cancelled: "रद्द",
    substitute: "घेतील:",
    room: "खोली",
    batch: "बॅच",
    noDivision: "तुम्हाला अजून कोणत्याही तुकडीत ठेवलेले नाही. कृपया कॉलेज ऑफिसशी संपर्क साधा.",
  },
};
