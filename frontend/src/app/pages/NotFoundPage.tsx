import SimplePage from "./SimplePage";
import { browserLanguage, NOT_FOUND } from "./simplePages";

export default function NotFoundPage() {
  return <SimplePage strings={NOT_FOUND} language={browserLanguage()} />;
}
