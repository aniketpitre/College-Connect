import { useParams } from "react-router";
import SimplePage from "./SimplePage";
import { browserLanguage, VERIFY } from "./simplePages";

export default function VerifyPage() {
  const { code } = useParams();
  return (
    <SimplePage strings={VERIFY} language={browserLanguage()}>
      <p className="mono-note">{code}</p>
    </SimplePage>
  );
}
