import { LoginCard } from "@/components/auth/login-card";

export default function AdminLoginPage() {
  return (
    <LoginCard
      title="Admin Login"
      description="Use the admin username and password gate before accessing scenario runs, evaluations, and borrower creation."
      fields={[
        { label: "Username", type: "text", placeholder: "admin" },
        { label: "Password", type: "password", placeholder: "Enter admin password" },
      ]}
      submitLabel="Enter Admin Console"
      afterSubmitHref="/admin"
    />
  );
}
