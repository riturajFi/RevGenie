import { LoginCard } from "@/components/auth/login-card";

export default function BorrowerLoginPage() {
  return (
    <LoginCard
      title="Borrower Login"
      description="Borrower access stays intentionally simple: borrower ID plus the shared password gate before chat."
      fields={[
        { label: "Borrower ID", type: "text", placeholder: "b_001" },
        { label: "Password", type: "password", placeholder: "Enter borrower password" },
      ]}
      submitLabel="Continue To Chat"
    />
  );
}
