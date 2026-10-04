import { useEffect, useState } from "react";
import "./App.css";
import Admin from "./Admin";
import HelpDesk from "./HelpDesk";

const isAdminRoute = () => window.location.hash.startsWith("#/admin");

function App() {
  const [admin, setAdmin] = useState(isAdminRoute);

  useEffect(() => {
    const onHash = () => setAdmin(isAdminRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return admin ? <Admin /> : <HelpDesk />;
}

export default App;
