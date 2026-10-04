import { EmptyState } from "../../components/EmptyState";
import { useMe } from "../../lib/auth";
import { useLanguage } from "../../lib/language";

const STRINGS = {
  en: { welcome: "Welcome", soon: "Your dashboard is on its way", body: "Fees, receipts and notices arrive later in Phase 1." },
  hi: { welcome: "स्वागत है", soon: "आपका डैशबोर्ड जल्द आ रहा है", body: "फ़ीस, रसीदें और सूचनाएं चरण 1 में आगे आएंगी।" },
  mr: { welcome: "स्वागत आहे", soon: "तुमचा डॅशबोर्ड लवकरच येत आहे", body: "शुल्क, पावत्या आणि सूचना टप्पा 1 मध्ये पुढे येतील." },
};

/** Replaced by the student and staff dashboards in plan item 1.12. */
export default function PortalHome() {
  const { data: me } = useMe();
  const [language] = useLanguage();
  const t = STRINGS[language];
  return (
    <div lang={language}>
      <div className="eyebrow">CollegeConnect</div>
      <h1>
        {t.welcome}, {me?.name.split(" ")[0]}
      </h1>
      <EmptyState title={t.soon}>{t.body}</EmptyState>
    </div>
  );
}
