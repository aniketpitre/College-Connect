import { Navigate, Route, Routes, useLocation } from "react-router";
import AccountPage from "../features/account/AccountPage";
import AnalyticsPage from "../features/analytics/AnalyticsPage";
import ApprovalsPage from "../features/approvals/ApprovalsPage";
import AttendancePage from "../features/attendance/AttendancePage";
import TakeAttendancePage from "../features/attendance/TakeAttendancePage";
import AuditPage from "../features/audit/AuditPage";
import CertificatesPage from "../features/certificates/CertificatesPage";
import ExamSessionPage from "../features/exams/ExamSessionPage";
import ExamsPage from "../features/exams/ExamsPage";
import MarksSheetPage from "../features/exams/MarksSheetPage";
import TimetableEditorPage from "../features/timetable/TimetableEditorPage";
import TimetablePage from "../features/timetable/TimetablePage";
import ExportsPage from "../features/exports/ExportsPage";
import CollectPage from "../features/fees/CollectPage";
import FeeSetupPage from "../features/fees/FeeSetupPage";
import FeesHome from "../features/fees/FeesHome";
import OpeningPage from "../features/fees/OpeningPage";
import OnlinePaymentsPage from "../features/fees/OnlinePaymentsPage";
import MessagesPage from "../features/messages/MessagesPage";
import HostelPage from "../features/campus/HostelPage";
import GrievancePage from "../features/grievance/GrievancePage";
import LeavePage from "../features/staff/LeavePage";
import StaffPage from "../features/staff/StaffPage";
import AccreditationPage from "../features/reports/ReportsPage";
import LibraryPage from "../features/campus/LibraryPage";
import PlacementPage from "../features/campus/PlacementPage";
import AdmissionsPage from "../features/admissions/AdmissionsPage";
import ApplicationDetailPage from "../features/admissions/ApplicationDetailPage";
import MyApplicationPage from "../features/admissions/MyApplicationPage";
import ApplyPage from "./pages/ApplyPage";
import ReportsPage from "../features/fees/ReportsPage";
import StudentFeesPage from "../features/fees/StudentFeesPage";
import NoticeDetailPage from "../features/notices/NoticeDetailPage";
import NoticesPage from "../features/notices/NoticesPage";
import MyFeesPage from "../features/portal/MyFeesPage";
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
import WelcomePage from "./pages/WelcomePage";
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
      <Route path="/apply" element={<ApplyPage />} />
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
      <Route
        path="/app/welcome"
        element={
          <RequireAuth>
            <WelcomePage />
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
        <Route path="my-fees" element={<MyFeesPage />} />
        <Route path="notices" element={<NoticesPage />} />
        <Route path="notices/:id" element={<NoticeDetailPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="setup" element={<InstitutionSetupPage />} />
        <Route path="fees" element={<FeesHome />} />
        <Route path="fees/setup" element={<FeeSetupPage />} />
        <Route path="fees/collect/:id" element={<CollectPage />} />
        <Route path="fees/reports" element={<ReportsPage />} />
        <Route path="fees/online" element={<OnlinePaymentsPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="hostel" element={<HostelPage />} />
        <Route path="grievances" element={<GrievancePage />} />
        <Route path="leave" element={<LeavePage />} />
        <Route path="staff" element={<StaffPage />} />
        <Route path="reports" element={<AccreditationPage />} />
        <Route path="placement" element={<PlacementPage />} />
        <Route path="application" element={<MyApplicationPage />} />
        <Route path="admissions" element={<AdmissionsPage />} />
        <Route path="admissions/applications/:id" element={<ApplicationDetailPage />} />
        <Route path="fees/opening" element={<OpeningPage />} />
        <Route path="fees/students/:id" element={<StudentFeesPage />} />
        <Route path="approvals" element={<ApprovalsPage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="students/import" element={<ImportPage />} />
        <Route path="students/promote" element={<PromotePage />} />
        <Route path="students/:id" element={<StudentDetailPage />} />
        <Route path="attendance" element={<AttendancePage />} />
        <Route path="attendance/take/:slotId/:date" element={<TakeAttendancePage />} />
        <Route path="certificates" element={<CertificatesPage />} />
        <Route path="exams" element={<ExamsPage />} />
        <Route path="exams/marks/:divisionId/:subjectId" element={<MarksSheetPage />} />
        <Route path="exams/sessions/:id" element={<ExamSessionPage />} />
        <Route path="timetable" element={<TimetablePage />} />
        <Route path="timetable/:id" element={<TimetableEditorPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="exports" element={<ExportsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
