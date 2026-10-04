import SimplePage from "./SimplePage";
import { browserLanguage, LOGIN } from "./simplePages";

export default function LoginPage() {
  return <SimplePage strings={LOGIN} language={browserLanguage()} />;
}
