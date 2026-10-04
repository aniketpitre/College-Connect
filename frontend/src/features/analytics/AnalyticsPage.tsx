import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { UI_STRINGS } from "../../i18n";
import { apiFetch } from "../../lib/api";
import type { AdminStats, Category, LoggedQuery } from "../../lib/types";
import "./analytics.css";

const LANG_NAMES = { en: "English", hi: "Hindi", mr: "Marathi" } as const;
const OFFICE_NAMES = Object.fromEntries(UI_STRINGS.en.officesList.map((o) => [o.category, o.title])) as Record<Category, string>;

const fmtLatency = (ms: number) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Help-desk analytics (permission: analytics.view). */
export default function AnalyticsPage() {
  const [days, setDays] = useState(7);
  const query = useQuery({
    queryKey: ["admin", "stats", days],
    queryFn: () => apiFetch<AdminStats>(`/admin/stats?days=${days}`),
  });
  const stats = query.data;
  const byCategory = Object.entries(stats?.by_category ?? {}).sort((a, b) => b[1] - a[1]) as [Category, number][];
  const maxCat = Math.max(1, ...byCategory.map(([, n]) => n));

  return (
    <div className="analytics">
      <div className="page-head">
        <div>
          <div className="eyebrow">Campus overview</div>
          <h1>Help desk analytics</h1>
        </div>
        <div className="admin-actions">
          <div className="seg" role="group" aria-label="Time range">
            {[7, 30, 90].map((d) => (
              <button key={d} type="button" className={d === days ? "active" : ""} aria-pressed={d === days} onClick={() => setDays(d)}>
                {d}d
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => query.refetch()} disabled={query.isFetching}>
            {query.isFetching ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>
      {query.error && <p className="admin-error">{query.error.message}</p>}
      {query.isLoading && <p className="muted">Loading…</p>}

      {stats && (
        <>
          <p className="muted pipeline-line">
            Retrieval: <b>{stats.pipeline.retrieval === "vector" ? `vector (${stats.pipeline.embedding_model})` : "keyword (BM25)"}</b>
            {" · "}Answers: <b>{stats.pipeline.generation === "extractive" ? "document excerpts (no LLM key)" : stats.pipeline.generation}</b>
          </p>

            {!stats.analytics_enabled ? (
              <div className="admin-card">
                <h3>Analytics are off</h3>
                <p className="muted">Set MONGODB_URI on the server to record questions and see usage here.</p>
              </div>
            ) : (
              <>
                <div className="tiles">
                  <Tile label={`Questions, last ${stats.days} days`} value={stats.total_queries?.toLocaleString() ?? "0"} note={`${stats.all_time_queries?.toLocaleString()} all time`} />
                  <Tile
                    label="Answered from documents"
                    value={stats.grounded_rate == null ? "—" : `${Math.round(stats.grounded_rate * 100)}%`}
                    note="Share of questions with a cited source"
                  />
                  <Tile
                    label="Average response time"
                    value={stats.avg_latency_ms == null ? "—" : fmtLatency(stats.avg_latency_ms)}
                    note="Target: under 5 s"
                  />
                  <Tile label="Documents indexed" value={String(stats.pipeline.documents)} note={`${stats.pipeline.chunks} searchable sections`} />
                </div>

                <div className="admin-grid">
                  <section className="admin-card" aria-labelledby="by-office">
                    <h3 id="by-office">Questions by office</h3>
                    {byCategory.length === 0 ? (
                      <p className="muted">No questions in this period.</p>
                    ) : (
                      <ul className="barlist">
                        {byCategory.map(([cat, n]) => (
                          <li key={cat} title={`${OFFICE_NAMES[cat] ?? cat}: ${n} questions`}>
                            <span className="barlist-label">{OFFICE_NAMES[cat] ?? cat}</span>
                            <span className="barlist-track">
                              <span className="barlist-bar" style={{ width: `${(n / maxCat) * 100}%` }} />
                            </span>
                            <span className="barlist-value">{n}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <h3 className="sub">By language</h3>
                    <p className="lang-line">
                      {Object.entries(stats.by_language ?? {}).map(([lang, n]) => (
                        <span key={lang}>
                          {LANG_NAMES[lang as keyof typeof LANG_NAMES] ?? lang} <b>{n}</b>
                        </span>
                      ))}
                    </p>
                  </section>

                  <section className="admin-card" aria-labelledby="gaps">
                    <h3 id="gaps">Knowledge gaps</h3>
                    <p className="muted small">Questions no document could answer — candidates for a new notice or FAQ.</p>
                    <QueryList rows={stats.knowledge_gaps ?? []} empty="Every question in this period was answered from a document." />
                  </section>
                </div>

                <section className="admin-card" aria-labelledby="recent">
                  <h3 id="recent">Recent questions</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>When</th>
                          <th>Question</th>
                          <th>Office</th>
                          <th>Lang</th>
                          <th>Answer</th>
                          <th className="num">Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(stats.recent ?? []).map((q, i) => (
                          <tr key={i}>
                            <td className="nowrap">{fmtTime(q.created_at)}</td>
                            <td>{q.question}</td>
                            <td>{q.category ? OFFICE_NAMES[q.category] : "—"}</td>
                            <td>{q.language.toUpperCase()}</td>
                            <td>
                              <span className={q.grounded ? "badge grounded" : "badge ungrounded"}>{q.grounded ? "Cited" : "No source"}</span>
                            </td>
                            <td className="num">{fmtLatency(q.latency_ms)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {(stats.recent ?? []).length === 0 && <p className="muted">No questions yet.</p>}
                  </div>
                </section>
              </>
            )}
        </>
      )}
    </div>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      <div className="tile-note">{note}</div>
    </div>
  );
}

function QueryList({ rows, empty }: { rows: LoggedQuery[]; empty: string }) {
  if (rows.length === 0) return <p className="muted">{empty}</p>;
  return (
    <ul className="qlist">
      {rows.map((q, i) => (
        <li key={i}>
          <span className="q">{q.question}</span>
          <span className="q-meta">
            {fmtTime(q.created_at)} · {q.language.toUpperCase()}
            {q.category_filter ? ` · filtered to ${OFFICE_NAMES[q.category_filter]}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
