import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { MoneyText } from "../../components/MoneyText";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError, apiFetch } from "../../lib/api";
import { useLanguage } from "../../lib/language";
import LanguageToggle from "../LanguageToggle";
import "../layout.css";
import { VERIFY } from "./simplePages";

interface ReceiptCheck {
  type: "receipt";
  valid: boolean;
  status: string;
  number: string;
  date: string;
  amount: number;
  academic_year: string;
  student_name: string;
  prn: string;
  college: string;
  cancelled_at: string | null;
}

interface CertificateCheck {
  type: "certificate";
  valid: boolean;
  status: string;
  number: string;
  date: string;
  certificate: string;
  student_name: string;
  prn: string;
  college: string;
}

type Verification = ReceiptCheck | CertificateCheck;

/** Public: opened from the QR code on a receipt or certificate. Says whether it is genuine and still valid. */
export default function VerifyPage() {
  const { code = "" } = useParams();
  const [language, setLanguage] = useLanguage();
  const t = VERIFY[language];
  const result = useQuery({
    queryKey: ["verify", code],
    queryFn: () => apiFetch<Verification>(`/verify/${encodeURIComponent(code)}`),
    retry: false,
  });
  const v = result.data;
  const locale = language === "en" ? "en-IN" : `${language}-IN`;
  const notFound = result.error instanceof ApiError && result.error.status === 404;

  return (
    <div className="simple-page" lang={language}>
      <div className="simple-card verify-card">
        <div className="verify-top">
          <Link className="brand" to="/">
            <span className="seal">CC</span> CollegeConnect
          </Link>
          <LanguageToggle value={language} onChange={setLanguage} />
        </div>
        <h1>{t.title}</h1>
        {result.isLoading && <p>{t.checking}</p>}
        {notFound && <p className="form-error">{t.notFound}</p>}
        {result.error && !notFound && <p className="form-error">{result.error.message}</p>}
        {v && v.type === "certificate" && (
          <>
            <div className={`verify-result ${v.valid ? "ok" : "bad"}`} role="status">
              <StatusBadge tone={v.valid ? "success" : "danger"}>{v.valid ? `✓ ${t.genuineCert}` : `✕ ${t.revokedCert}`}</StatusBadge>
            </div>
            <dl className="verify-list">
              <dt>{t.issuedBy}</dt>
              <dd>{v.college}</dd>
              <dt>{t.document}</dt>
              <dd>{v.certificate}</dd>
              <dt>{t.certNo}</dt>
              <dd className="mono">{v.number}</dd>
              <dt>{t.date}</dt>
              <dd>{new Date(v.date).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" })}</dd>
              <dt>{t.student}</dt>
              <dd>
                {v.student_name} · {v.prn}
              </dd>
            </dl>
          </>
        )}
        {v && v.type === "receipt" && (
          <>
            <div className={`verify-result ${v.valid ? "ok" : "bad"}`} role="status">
              <StatusBadge tone={v.valid ? "success" : "danger"}>{v.valid ? `✓ ${t.genuine}` : `✕ ${t.cancelled}`}</StatusBadge>
            </div>
            <dl className="verify-list">
              <dt>{t.issuedBy}</dt>
              <dd>{v.college}</dd>
              <dt>{t.receipt}</dt>
              <dd className="mono">{v.number}</dd>
              <dt>{t.date}</dt>
              <dd>{new Date(v.date).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" })}</dd>
              <dt>{t.amount}</dt>
              <dd>
                <MoneyText paise={v.amount} />
              </dd>
              <dt>{t.student}</dt>
              <dd>
                {v.student_name} · {v.prn}
              </dd>
              <dt>{t.year}</dt>
              <dd>{v.academic_year}</dd>
              {v.cancelled_at && (
                <>
                  <dt>{t.cancelledOn}</dt>
                  <dd>{new Date(v.cancelled_at).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" })}</dd>
                </>
              )}
            </dl>
          </>
        )}
        <p className="mono-note">{code}</p>
        <Link to="/">{t.back} →</Link>
      </div>
    </div>
  );
}
