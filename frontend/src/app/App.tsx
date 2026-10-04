import { Navigate, Route, Routes, useLocation } from "react-router";
import AccountPage from "../features/account/AccountPage";
import AnalyticsPage from "../features/analytics/AnalyticsPage";
import ProfilePage from "../features/profile/ProfilePage";
import HelpDesk from "../features/helpdesk/HelpDesk";
import InstitutionSetupPage from "../features/setup/InstitutionSetupPage";
import ImportPage from "../features/students/ImportPage";
import PromotePage from "../features/students/PromotePage";
import StudentDetailPage from "../features/students/StudentDetailPage";
import StudentsPage from "../features/students/StudentsPage";
import UsersPage from "../features/users/UsersPage";
import AppLayout from "./AppLayout";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import PortalHome from "./pages/PortalHome";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import SetupPage from "./pages/SetupPage";
import TwoStepPage from "./pages/TwoStepPage";
import VerifyPage from "./pages/VerifyPage";
import RequireAuth from "./RequireAuth";

/** Old links used "/#/admin"; send them to the new address. */
function HomeOrLegacyRedirect() {
  const { hash } = useLocation();
  if (hash.startsWith("#/admin")) return <Navigate to="/app/analytics" replace />;
  return <HelpDesk />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeOrLegacyRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/login/2-step" element={<TwoStepPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
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
      <Route path="/app/admin" element={<Navigate to="/app/analytics" replace />} />
      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<PortalHome />} />
        <Route path="account" element={<AccountPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="setup" element={<InstitutionSetupPage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="students/import" element={<ImportPage />} />
        <Route path="students/promote" element={<PromotePage />} />
        <Route path="students/:id" element={<StudentDetailPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
