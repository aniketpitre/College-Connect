import { Navigate, Route, Routes, useLocation } from "react-router";
import Admin from "../features/admin/Admin";
import HelpDesk from "../features/helpdesk/HelpDesk";
import AppLayout from "./AppLayout";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import PortalHome from "./pages/PortalHome";
import SetupPage from "./pages/SetupPage";
import TwoStepPage from "./pages/TwoStepPage";
import VerifyPage from "./pages/VerifyPage";
import RequireAuth from "./RequireAuth";

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
      <Route path="/login/2-step" element={<TwoStepPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/verify/:code" element={<VerifyPage />} />
      <Route
        path="/app/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />
      <Route path="/app/admin" element={<Admin />} />
      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<PortalHome />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
