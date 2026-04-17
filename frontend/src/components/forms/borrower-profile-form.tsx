"use client";

import { FormEvent, useState } from "react";

import { createBorrowerProfile } from "@/lib/api";
import { borrowerCreateDefaults, borrowerTestDefaults } from "@/lib/sample-data";
import { BorrowerProfileCreateInput } from "@/types/borrower";

type BorrowerCaseOverrideForm = {
  workflowId: string;
  lenderId: string;
  loanIdMasked: string;
  amountDue: string;
  stage: "" | "ASSESSMENT" | "RESOLUTION" | "FINAL_NOTICE";
  caseStatus: "" | "OPEN" | "RESOLVED" | "CLOSED" | "STOP_CONTACT";
};

const emptyCaseOverrideForm: BorrowerCaseOverrideForm = {
  workflowId: "",
  lenderId: "",
  loanIdMasked: "",
  amountDue: "",
  stage: "",
  caseStatus: "",
};

export function BorrowerProfileForm() {
  const [form, setForm] = useState({ ...borrowerCreateDefaults });
  const [caseOverrides, setCaseOverrides] = useState<BorrowerCaseOverrideForm>(emptyCaseOverrideForm);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createdBorrowerId, setCreatedBorrowerId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField<Key extends keyof typeof form>(key: Key, value: (typeof form)[Key]) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function updateCaseOverrideField<Key extends keyof BorrowerCaseOverrideForm>(
    key: Key,
    value: BorrowerCaseOverrideForm[Key]
  ) {
    setCaseOverrides((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function toOptionalNumber(value: string): number | undefined {
    const normalized = value.trim();
    if (!normalized) return undefined;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  function buildPayload(): BorrowerProfileCreateInput {
    return {
      fullName: form.fullName,
      phoneNumber: form.phoneNumber,
      caseOverrides: {
        workflowId: caseOverrides.workflowId.trim() || undefined,
        lenderId: caseOverrides.lenderId.trim() || undefined,
        loanIdMasked: caseOverrides.loanIdMasked.trim() || undefined,
        amountDue: toOptionalNumber(caseOverrides.amountDue),
        stage: caseOverrides.stage || undefined,
        caseStatus: caseOverrides.caseStatus || undefined,
      },
    };
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setStatus("Saving borrower profile...");
    setCreatedBorrowerId(null);

    try {
      const result = await createBorrowerProfile(buildPayload());
      setCreatedBorrowerId(result.borrower_id);
      setStatus("Borrower profile and borrower case created.");
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "Failed to create borrower profile and borrower case"
      );
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
          The backend generates the borrower ID and now auto-creates borrower case data from `b_001` defaults. Keep
          case override fields blank to use defaults, or edit any field before saving.
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
          <h3>Borrower Case Overrides (Optional)</h3>
          <p>
            If left empty, case creation uses `b_001` defaults. Fill any field below to override defaults for this
            borrower case.
          </p>
          <div className="field-grid">
            <label className="field">
              <span>Workflow ID</span>
              <input
                type="text"
                placeholder={borrowerTestDefaults.workflowId}
                value={caseOverrides.workflowId}
                onChange={(event) => updateCaseOverrideField("workflowId", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Lender ID</span>
              <input
                type="text"
                placeholder={borrowerTestDefaults.lenderId}
                value={caseOverrides.lenderId}
                onChange={(event) => updateCaseOverrideField("lenderId", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Masked Loan ID</span>
              <input
                type="text"
                placeholder={borrowerTestDefaults.loanIdMasked}
                value={caseOverrides.loanIdMasked}
                onChange={(event) => updateCaseOverrideField("loanIdMasked", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Amount Due</span>
              <input
                type="number"
                min={0}
                placeholder={String(borrowerTestDefaults.amountDue)}
                value={caseOverrides.amountDue}
                onChange={(event) => updateCaseOverrideField("amountDue", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Stage</span>
              <select
                className="select-input"
                value={caseOverrides.stage}
                onChange={(event) =>
                  updateCaseOverrideField(
                    "stage",
                    event.target.value as BorrowerCaseOverrideForm["stage"]
                  )
                }
              >
                <option value="">Use default ({borrowerTestDefaults.stage})</option>
                <option value="ASSESSMENT">ASSESSMENT</option>
                <option value="RESOLUTION">RESOLUTION</option>
                <option value="FINAL_NOTICE">FINAL_NOTICE</option>
              </select>
            </label>
            <label className="field">
              <span>Case Status</span>
              <select
                className="select-input"
                value={caseOverrides.caseStatus}
                onChange={(event) =>
                  updateCaseOverrideField(
                    "caseStatus",
                    event.target.value as BorrowerCaseOverrideForm["caseStatus"]
                  )
                }
              >
                <option value="">Use default ({borrowerTestDefaults.caseStatus})</option>
                <option value="OPEN">OPEN</option>
                <option value="RESOLVED">RESOLVED</option>
                <option value="CLOSED">CLOSED</option>
                <option value="STOP_CONTACT">STOP_CONTACT</option>
              </select>
            </label>
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" className="button button-primary" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : "Save Borrower"}
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              setForm({ ...borrowerCreateDefaults });
              setCaseOverrides(emptyCaseOverrideForm);
            }}
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
