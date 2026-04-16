"use client";

import { FormEvent, useState } from "react";

import { createBorrowerProfile } from "@/lib/api";
import { borrowerCreateDefaults, borrowerTestDefaults } from "@/lib/sample-data";
import { BorrowerProfileCreateInput } from "@/types/borrower";

type OptionalField = {
  key: keyof typeof borrowerTestDefaults;
  label: string;
};

const optionalFields: OptionalField[] = [
  { key: "lenderId", label: "Lender ID" },
  { key: "workflowId", label: "Workflow ID" },
  { key: "loanIdMasked", label: "Masked Loan ID" },
  { key: "amountDue", label: "Amount Due" },
  { key: "principalOutstanding", label: "Principal Outstanding" },
  { key: "dpd", label: "DPD" },
  { key: "caseType", label: "Case Type" },
  { key: "stage", label: "Stage" },
  { key: "caseStatus", label: "Case Status" },
  { key: "nextAllowedActions", label: "Next Allowed Actions" },
];

export function BorrowerProfileForm() {
  const [form, setForm] = useState<BorrowerProfileCreateInput>(borrowerCreateDefaults);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createdBorrowerId, setCreatedBorrowerId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField<Key extends keyof BorrowerProfileCreateInput>(key: Key, value: BorrowerProfileCreateInput[Key]) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setStatus("Saving borrower profile...");
    setCreatedBorrowerId(null);

    try {
      const result = await createBorrowerProfile(form);
      setCreatedBorrowerId(result.borrower_id);
      setStatus("Borrower profile created.");
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Failed to create borrower profile");
      setStatus(null);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="panel form-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Create Borrower Profile</h2>
        </div>
        <p className="panel-copy">
          The backend generates the borrower ID. The form only asks for the required identity fields, while the
          testing defaults below stay ready for the next backend step.
        </p>
      </div>

      <form className="borrower-form" onSubmit={handleSubmit}>
        <label className="field field-highlight">
          <span>Phone Number</span>
          <input
            type="tel"
            placeholder="+919900000001"
            required
            value={form.phoneNumber}
            onChange={(event) => updateField("phoneNumber", event.target.value)}
          />
          <small>This is the primary required field.</small>
        </label>

        <label className="field">
          <span>Full Name</span>
          <input
            type="text"
            placeholder="Aarav Sharma"
            required
            value={form.fullName}
            onChange={(event) => updateField("fullName", event.target.value)}
          />
        </label>

        <div className="autofill-note">
          <h3>Testing Defaults Preview</h3>
          <p>
            These values are prefilled from the backend sample case data and are kept ready for the next borrower
            setup step.
          </p>
          <div className="preview-grid">
            {optionalFields.map((field) => (
              <div className="preview-item" key={field.key}>
                <span>{field.label}</span>
                <strong>{String(borrowerTestDefaults[field.key])}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" className="button button-primary" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : "Save Borrower"}
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => setForm(borrowerCreateDefaults)}
            disabled={isSubmitting}
          >
            Reset
          </button>
        </div>

        {status ? <p className="form-status">{status}</p> : null}
        {createdBorrowerId ? (
          <p className="form-success">
            Generated borrower ID: <strong>{createdBorrowerId}</strong>
          </p>
        ) : null}
        {error ? <p className="form-error">{error}</p> : null}
      </form>
    </section>
  );
}
