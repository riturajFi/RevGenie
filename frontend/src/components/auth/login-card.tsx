import Link from "next/link";

type LoginCardProps = {
  title: string;
  description: string;
  fields: Array<{
    label: string;
    type: string;
    placeholder: string;
  }>;
  submitLabel: string;
  backHref?: string;
  afterSubmitHref?: string;
};

export function LoginCard({
  title,
  description,
  fields,
  submitLabel,
  backHref = "/",
  afterSubmitHref,
}: LoginCardProps) {
  return (
    <section className="login-shell">
      <div className="panel login-panel">
        <p className="eyebrow">Access</p>
        <h1>{title}</h1>
        <p className="panel-copy">{description}</p>

        <form className="login-form">
          {fields.map((field) => (
            <label className="field" key={field.label}>
              <span>{field.label}</span>
              <input type={field.type} placeholder={field.placeholder} />
            </label>
          ))}

          <div className="form-actions">
            {afterSubmitHref ? (
              <Link href={afterSubmitHref} className="button button-primary">
                {submitLabel}
              </Link>
            ) : (
              <button type="button" className="button button-primary">
                {submitLabel}
              </button>
            )}
            <Link href={backHref} className="button button-secondary">
              Back
            </Link>
          </div>
        </form>
      </div>
    </section>
  );
}
