import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ATTENDANCE_KEY, syncOutbox } from "../../lib/attendance";

/** Sends attendance saved offline as soon as the phone is back online (and every minute). */
export function OfflineSync() {
  const qc = useQueryClient();
  useEffect(() => {
    const sync = () => {
      if (!navigator.onLine) return;
      void syncOutbox().then((r) => {
        if (r.sent || r.problems) void qc.invalidateQueries({ queryKey: ATTENDANCE_KEY });
      });
    };
    sync();
    window.addEventListener("online", sync);
    const timer = window.setInterval(sync, 60_000);
    return () => {
      window.removeEventListener("online", sync);
      window.clearInterval(timer);
    };
  }, [qc]);
  return null;
}
