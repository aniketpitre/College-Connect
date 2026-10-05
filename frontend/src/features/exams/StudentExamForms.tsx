import { MARKS_STRINGS } from "../../i18n/marks";
import { myHallTicketUrl, useMyExams, useSubmitForm } from "../../lib/exams";
import { useLanguage } from "../../lib/language";
import { formatPaise } from "../../lib/money";

/** A student's exam forms: fill them, see what blocks eligibility, download the hall ticket. */
export default function StudentExamForms() {
  const [language] = useLanguage();
  const T = MARKS_STRINGS[language];
  const exams = useMyExams();
  const submit = useSubmitForm();
  if (!exams.data?.length) return null;
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  return (
    <>
      <h2 className="subhead">{T.examForms}</h2>
      {submit.error && <p className="form-error">{submit.error.message}</p>}
      <div className="request-list">
        {exams.data.map((x) => (
          <section key={x.id} className="card request-card">
            <div className="request-head">
              <b>{x.name}</b>
              <span className={`small ${x.form_status === "rejected" ? "att-critical" : "muted"}`}>{T.formStatus[x.form_status]}</span>
            </div>
            {x.reason && <p className="small">{x.reason}</p>}
            {x.form_status === "not_submitted" && <p className="small">{x.form_open ? T.formBy(day(x.form_deadline)) : T.formClosed}</p>}
            {!x.attendance_ok && <p className="small att-critical">{T.lowAttendance(x.low_subjects.join(", "))}</p>}
            {!x.fee_ok && <p className="small att-critical">{T.feeDue(formatPaise(x.fee_due))}</p>}
            <div className="small muted">{T.yourSubjects}</div>
            <ul className="marks-parts">
              {x.subjects.map((s) => {
                const paper = x.papers.find((p) => p.code === s.code);
                return (
                  <li key={s.code}>
                    <span>
                      {s.code} {s.name}
                      {s.backlog && ` (${T.backlog})`}
                    </span>
                    {paper && (
                      <b>
                        {day(paper.date)} {paper.start}
                      </b>
                    )}
                  </li>
                );
              })}
            </ul>
            {x.seat_no && (
              <p className="small">
                {T.seatNo}: <b>{x.seat_no}</b>
              </p>
            )}
            <div className="row-actions">
              {x.form_open && (x.form_status === "not_submitted" || x.form_status === "rejected") && (
                <button type="button" className="btn btn-primary btn-sm" disabled={submit.isPending} onClick={() => submit.mutate(x.id)}>
                  {T.submitForm}
                </button>
              )}
              {x.hall_ticket && (
                <a className="btn btn-primary btn-sm" href={myHallTicketUrl(x.id)} target="_blank" rel="noreferrer">
                  {T.hallTicket}
                </a>
              )}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
