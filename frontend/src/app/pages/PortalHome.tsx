import { EmptyState } from "../../components/EmptyState";
import { useMe } from "../../lib/auth";

export default function PortalHome() {
  const { data: me } = useMe();
  return (
    <>
      <div className="eyebrow">CollegeConnect</div>
      <h1>Welcome, {me?.name.split(" ")[0]}</h1>
      <EmptyState title="Your dashboard is on its way">
        Student records, fees and receipts arrive in the next part of Phase 1.
      </EmptyState>
    </>
  );
}
