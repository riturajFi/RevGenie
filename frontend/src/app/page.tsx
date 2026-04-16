import Link from "next/link";

export default function HomePage() {
  return (
    <main className="landing-page">
      <section className="hero panel">
        <p className="eyebrow">RevGenie</p>
        <h1>Collections demo frontend</h1>
        <p className="hero-copy">
          Start from a simple role split. Borrowers go to chat access. Admin goes to the evaluation console and
          borrower setup tools.
        </p>

        <div className="hero-actions">
          <Link href="/admin/login" className="button button-primary">
            Login As Admin
          </Link>
          <Link href="/borrower/login" className="button button-secondary">
            Login As Borrower
          </Link>
        </div>
      </section>
    </main>
  );
}
