"use client";

import { useEffect, useState } from "react";

import { getLenderPolicy, listLenderPolicies, upsertLenderPolicy } from "@/lib/api";

function toSortedUniqueLenderIds(lenderIds: string[]): string[] {
  return [...new Set(lenderIds)].sort((a, b) => a.localeCompare(b));
}

export function LenderPolicyDashboard() {
  const [knownLenderIds, setKnownLenderIds] = useState<string[]>([]);
  const [lenderId, setLenderId] = useState("nira");
  const [policyText, setPolicyText] = useState("");
  const [isBootLoading, setIsBootLoading] = useState(true);
  const [isLoadingPolicy, setIsLoadingPolicy] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setIsBootLoading(true);
      setError(null);
      try {
        const policies = await listLenderPolicies();
        if (cancelled) {
          return;
        }

        const sortedIds = toSortedUniqueLenderIds(policies.map((item) => item.lender_id));
        setKnownLenderIds(sortedIds);

        if (sortedIds.length === 0) {
          setPolicyText("");
          setStatus("No lender policy found yet. Enter a lender ID and save a policy.");
          return;
        }

        const initialLenderId = sortedIds.includes("nira") ? "nira" : sortedIds[0];
        const initialPolicy = policies.find((item) => item.lender_id === initialLenderId);
        setLenderId(initialLenderId);
        setPolicyText(initialPolicy?.policy ?? "");
        setStatus(`Loaded policy for ${initialLenderId}.`);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load lender policies");
        }
      } finally {
        if (!cancelled) {
          setIsBootLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  function appendKnownLenderId(nextLenderId: string) {
    setKnownLenderIds((current) => toSortedUniqueLenderIds([...current, nextLenderId]));
  }

  async function handleLoadPolicy(targetLenderId?: string) {
    const resolvedLenderId = (targetLenderId ?? lenderId).trim();
    if (!resolvedLenderId) {
      setError("Enter a lender ID to load policy.");
      setStatus(null);
      return;
    }

    setIsLoadingPolicy(true);
    setError(null);
    setStatus(null);

    try {
      const record = await getLenderPolicy(resolvedLenderId);
      if (record === null) {
        setPolicyText("");
        setStatus(`No saved policy for ${resolvedLenderId}. Add text and click save to create one.`);
      } else {
        setPolicyText(record.policy);
        appendKnownLenderId(record.lender_id);
        setStatus(`Loaded policy for ${record.lender_id}.`);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load lender policy");
    } finally {
      setIsLoadingPolicy(false);
    }
  }

  async function handleSavePolicy() {
    const resolvedLenderId = lenderId.trim();
    const resolvedPolicyText = policyText.trim();

    if (!resolvedLenderId) {
      setError("Lender ID is required.");
      setStatus(null);
      return;
    }
    if (!resolvedPolicyText) {
      setError("Policy text is required.");
      setStatus(null);
      return;
    }

    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const result = await upsertLenderPolicy(resolvedLenderId, policyText);
      appendKnownLenderId(result.record.lender_id);
      setLenderId(result.record.lender_id);
      setPolicyText(result.record.policy);
      setStatus(
        result.mode === "created"
          ? `Created policy for ${result.record.lender_id}.`
          : `Updated policy for ${result.record.lender_id}.`
      );
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save lender policy");
    } finally {
      setIsSaving(false);
    }
  }

  if (isBootLoading) {
    return (
      <section className="panel placeholder-panel">
        <h2>Lender Policy</h2>
        <p>Loading lender policies...</p>
      </section>
    );
  }

  return (
    <section className="panel lender-policy-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Policy</p>
          <h2>Lender Policy Rules</h2>
        </div>
        <p className="panel-copy">
          Set company policy per lender. This policy is used during evaluation and lender-specific negotiation flows.
        </p>
      </div>

      <div className="lender-policy-controls">
        <label className="field">
          <span>Existing Lenders</span>
          <select
            className="select-input"
            value={knownLenderIds.includes(lenderId) ? lenderId : ""}
            onChange={(event) => {
              const selected = event.target.value;
              if (!selected) {
                return;
              }
              setLenderId(selected);
              void handleLoadPolicy(selected);
            }}
          >
            <option value="">Select a lender</option>
            {knownLenderIds.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Lender ID</span>
          <input
            type="text"
            placeholder="nira"
            value={lenderId}
            onChange={(event) => setLenderId(event.target.value)}
          />
        </label>
      </div>

      <label className="field">
        <span>Policy Text</span>
        <textarea
          className="lender-policy-textarea"
          rows={18}
          value={policyText}
          onChange={(event) => setPolicyText(event.target.value)}
        />
      </label>

      <div className="form-actions">
        <button
          type="button"
          className="button button-secondary"
          onClick={() => void handleLoadPolicy()}
          disabled={isLoadingPolicy}
        >
          {isLoadingPolicy ? "Loading..." : "Load Policy"}
        </button>
        <button type="button" className="button button-primary" onClick={() => void handleSavePolicy()} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Policy"}
        </button>
      </div>

      {status ? <p className="form-success">{status}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
    </section>
  );
}
