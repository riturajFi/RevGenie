"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { borrowerPortalLogin } from "@/lib/api";

const BORROWER_SESSION_STORAGE_KEY = "revgenie.borrower.session";
const BORROWER_SKIP_RESET_ONCE_KEY = "revgenie.borrower.skip_reset_once";

export function BorrowerLoginForm() {
  const router = useRouter();
  const [phoneNumber, setPhoneNumber] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const result = await borrowerPortalLogin(phoneNumber, password);
      sessionStorage.setItem(BORROWER_SESSION_STORAGE_KEY, JSON.stringify(result));
      sessionStorage.setItem(BORROWER_SKIP_RESET_ONCE_KEY, "1");
      router.push("/borrower/chat");
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Failed borrower login");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="login-shell">
      <div className="panel login-panel">
        <p className="eyebrow">Borrower Access</p>
        <h1>Borrower Login</h1>
        <p className="panel-copy">Login with your phone number and shared borrower password.</p>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Phone Number</span>
            <input
              type="tel"
              placeholder="+919900000001"
              value={phoneNumber}
              onChange={(event) => setPhoneNumber(event.target.value)}
              required
            />
          </label>

          <label className="field">
            <span>Password</span>
            <input
              type="password"
              placeholder="Enter borrower password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          <div className="form-actions">
            <button type="submit" className="button button-primary" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Continue To Chat"}
            </button>
            <Link href="/" className="button button-secondary">
              Back
            </Link>
          </div>

          {error ? <p className="form-error">{error}</p> : null}
        </form>
      </div>
    </section>
  );
}
