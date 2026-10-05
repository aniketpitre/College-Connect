import { useState } from "react";
import LanguageToggle from "../../app/LanguageToggle";
import { EmptyState } from "../../components/EmptyState";
import { ATTENDANCE_STRINGS } from "../../i18n/attendance";
import { useMyAttendance } from "../../lib/attendance";
import { useLanguage } from "../../lib/language";
import "./attendance.css";

/** A student's own attendance: subject-wise %, what they can miss or must attend, day by day. */
export default function StudentAttendance() {
  const [language, setLanguage] = useLanguage();
  const T = ATTENDANCE_STRINGS[language];
  const mine = useMyAttendance();
  const [allDays, setAllDays] = useState(false);
  const a = mine.data;
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "short" });

  return (
    <div lang={language}>
      <div className="page-head">
        <h1>{T.title}</h1>
        <LanguageToggle value={language} onChange={setLanguage} />
      </div>
      {mine.error && <p className="form-error">{mine.error.message}</p>}
      {a && a.subjects.length === 0 && <EmptyState title={T.noLectures} />}
      {a && a.subjects.length > 0 && (
        <>
          <p className="muted">
            {T.overall}: <b>{a.overall.percent}%</b> ({T.of(a.overall.attended, a.overall.held)}). {T.minimum(a.minimum)}
          </p>
          <div className="att-subjects">
            {a.subjects.map((s) => (
              <section key={s.subject_id} className={`card att-subject att-${s.status}`}>
                <div className="att-head">
                  <div>
                    <b>{s.code}</b> <span className="muted">{s.name}</span>
                  </div>
                  <div className="att-percent">{s.percent}%</div>
                </div>
                <div className="att-bar" role="img" aria-label={`${s.percent}%`}>
                  <span style={{ width: `${Math.min(100, s.percent ?? 0)}%` }} />
                  <i style={{ left: `${a.minimum}%` }} />
                </div>
                <div className="small muted">{T.of(s.attended, s.held)}</div>
                <p className="att-advice">
                  {s.must_attend > 0 ? T.mustAttend(s.must_attend) : s.can_miss > 0 ? T.canMiss(s.can_miss) : T.atMinimum}
                </p>
              </section>
            ))}
          </div>
          <p className="muted small">{T.exemptNote}</p>
          <h2 className="subhead">{T.recentDays}</h2>
          <ul className="att-days">
            {(allDays ? a.days : a.days.slice(0, 14)).map((d) => (
              <li key={d.date}>
                <span className="att-day">{day(d.date)}</span>
                {d.lectures.map((x, i) => (
                  <span key={i} className={`att-mark att-mark-${x.mark}`} title={T.marks[x.mark]}>
                    {x.code} {x.start} · {T.marks[x.mark]}
                  </span>
                ))}
              </li>
            ))}
          </ul>
          {!allDays && a.days.length > 14 && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAllDays(true)}>
              {T.showAll(a.days.length)}
            </button>
          )}
        </>
      )}
    </div>
  );
}
