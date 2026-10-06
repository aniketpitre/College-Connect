import { MARKS_STRINGS } from "../../i18n/marks";
import { useLanguage } from "../../lib/language";
import { myResultPdf, useMyResults, useRequestReval } from "../../lib/results";

/** A student's published results: CGPA, backlogs, each exam's papers, revaluation. */
export default function StudentResults() {
  const [language] = useLanguage();
  const T = MARKS_STRINGS[language];
  const results = useMyResults();
  const ask = useRequestReval();
  const r = results.data;
  if (!r || r.results.length === 0) return null;
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  return (
    <>
      <h2 className="subhead">{T.results}</h2>
      <div className="tiles fee-tiles">
        <div className="tile">
          <div className="tile-label">{T.cgpa}</div>
          <div className="tile-value">{r.cgpa?.toFixed(2) ?? "–"}</div>
        </div>
        <div className="tile">
          <div className="tile-label">{T.backlogs}</div>
          <div className="tile-value" style={{ fontSize: "1.2rem" }}>
            {r.backlogs.length ? r.backlogs.map((b) => b.code).join(", ") : T.noBacklogs}
          </div>
        </div>
      </div>
      {ask.error && <p className="form-error">{ask.error.message}</p>}
      {r.results.map((x) => (
        <section key={x.id} className="card result-card">
          <div className="request-head">
            <b>{x.exam}</b>
            <span>
              {T.sgpa} <b>{x.sgpa?.toFixed(2) ?? "–"}</b> · <span className={x.outcome === "pass" ? "" : "att-critical"}>{T.outcome[x.outcome]}</span>
            </span>
          </div>
          <div className="data-table-scroll">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th />
                  <th>Int</th>
                  <th>Ext</th>
                  <th>Total</th>
                  <th>{T.grade}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {x.subjects.map((s) => (
                  <tr key={s.code}>
                    <td>{s.code}</td>
                    <td>{s.name}</td>
                    <td>{s.internal ?? "–"}</td>
                    <td>{s.external ?? "–"}</td>
                    <td>{s.total ?? "–"}</td>
                    <td className={s.passed ? "" : "att-critical"}>{s.grade}</td>
                    <td>
                      {s.revaluation ? (
                        <span className="muted small">{s.revaluation.status_label}</span>
                      ) : (
                        s.can_request_revaluation && (
                          <button type="button" className="btn btn-ghost btn-sm" disabled={ask.isPending} onClick={() => ask.mutate({ resultId: x.id, code: s.code })}>
                            {T.askReval}
                          </button>
                        )
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row-actions" style={{ marginTop: 10 }}>
            {x.revaluation_until && <span className="muted small">{T.revalUntil(day(x.revaluation_until))}</span>}
            <a className="btn btn-ghost btn-sm" href={myResultPdf(x.id)} target="_blank" rel="noreferrer">
              {T.download}
            </a>
          </div>
        </section>
      ))}
    </>
  );
}
