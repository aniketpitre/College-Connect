import { Navigate, Route, Routes, useLocation } from "react-router";
import Admin from "../features/admin/Admin";
import HelpDesk from "../features/helpdesk/HelpDesk";
import AppLayout from "./AppLayout";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import PortalHome from "./pages/PortalHome";
import VerifyPage from "./pages/VerifyPage";

/** Old links used "/#/admin"; send them to the new address. */
function HomeOrLegacyRedirect() {
  const { hash } = useLocation();
  if (hash.startsWith("#/admin")) return <Navigate to="/app/admin" replace />;
  return <HelpDesk />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeOrLegacyRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/verify/:code" element={<VerifyPage />} />
      <Route path="/app/admin" element={<Admin />} />
      <Route path="/app" element={<AppLayout />}>
        <Route index element={<PortalHome />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
