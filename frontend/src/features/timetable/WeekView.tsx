import type { TimetableStrings } from "../../i18n/timetable";
import { dayNumber, type Lecture, type Week } from "../../lib/timetable";

interface Props {
  week: Week;
  T: TimetableStrings;
  /** Show the class on each lecture (a teacher's own week). */
  showDivision?: boolean;
  today: string;
  onLecture?: (lecture: Lecture) => void;
}

/** Monday–Saturday columns on wide screens, one day under another on phones. */
export function WeekView({ week, T, showDivision, today, onLecture }: Props) {
  return (
    <div className="week-grid">
      {week.days.map((day) => (
        <section key={day.date} className={`week-day${day.date === today ? " today" : ""}`} aria-label={`${T.days[dayNumber(day.date)]} ${day.date}`}>
          <h3>
            {T.days[dayNumber(day.date)]} <span className="muted">{shortDate(day.date)}</span>
          </h3>
          {day.holiday ? (
            <p className="week-holiday">
              {T.holiday}: {day.holiday}
            </p>
          ) : day.lectures.length === 0 ? (
            <p className="muted small">{T.noLectures}</p>
          ) : (
            day.lectures.map((x) => {
              const body = (
                <>
                  <div className="lecture-time">
                    {x.start}–{x.end}
                  </div>
                  <div className="lecture-subject">
                    <b>{x.subject_code}</b> {x.subject_name}
                  </div>
                  {showDivision && <div className="small">{x.division}</div>}
                  <div className="small muted">
                    {x.status === "substitute" ? `${T.substitute} ${x.substitute.join(", ")}` : x.faculty.join(", ")}
                    {x.room && ` · ${T.room} ${x.room}`}
                    {x.batch && ` · ${T.batch} ${x.batch}`}
                  </div>
                  {x.status === "cancelled" && <div className="lecture-flag">{T.cancelled}</div>}
                </>
              );
              const cls = `lecture lecture-${x.status}`;
              return onLecture ? (
                <button type="button" key={x.slot_id} className={cls} onClick={() => onLecture(x)}>
                  {body}
                </button>
              ) : (
                <div key={x.slot_id} className={cls}>
                  {body}
                </div>
              );
            })
          )}
        </section>
      ))}
    </div>
  );
}

function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
