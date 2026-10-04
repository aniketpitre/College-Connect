import type { Language } from "../lib/types";

export const NOTICE_STRINGS: Record<
  Language,
  { title: string; search: string; pinned: string; none: string; openPdf: string; back: string; postedOn: (d: string) => string; validTill: (d: string) => string }
> = {
  en: {
    title: "Notices",
    search: "Search notices",
    pinned: "Pinned",
    none: "No notices right now.",
    openPdf: "Open the PDF",
    back: "← Notices",
    postedOn: (d) => `Posted ${d}`,
    validTill: (d) => `until ${d}`,
  },
  hi: {
    title: "सूचनाएं",
    search: "सूचनाएं खोजें",
    pinned: "महत्वपूर्ण",
    none: "अभी कोई सूचना नहीं।",
    openPdf: "PDF खोलें",
    back: "← सूचनाएं",
    postedOn: (d) => `${d} को प्रकाशित`,
    validTill: (d) => `${d} तक`,
  },
  mr: {
    title: "सूचना",
    search: "सूचना शोधा",
    pinned: "महत्त्वाची",
    none: "सध्या कोणतीही सूचना नाही.",
    openPdf: "PDF उघडा",
    back: "← सूचना",
    postedOn: (d) => `${d} रोजी प्रसिद्ध`,
    validTill: (d) => `${d} पर्यंत`,
  },
};
