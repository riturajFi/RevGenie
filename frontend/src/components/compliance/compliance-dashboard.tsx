"use client";

import { useEffect, useState } from "react";

import { getComplianceConfig, resetComplianceConfig, updateComplianceConfig } from "@/lib/api";

export function ComplianceDashboard() {
  const [rulesText, setRulesText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const config = await getComplianceConfig();
        if (cancelled) return;
        setRulesText(config.rules_text);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load compliance rules");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    setIsSaving(true);
    setStatus(null);
    setError(null);
    try {
      const updated = await updateComplianceConfig(rulesText);
      setRulesText(updated.rules_text);
      setStatus("Global compliance rules updated.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to update compliance rules");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReset() {
    setIsResetting(true);
    setStatus(null);
    setError(null);
    try {
      const updated = await resetComplianceConfig();
      setRulesText(updated.rules_text);
      setStatus("Global compliance rules reset to default.");
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : "Failed to reset compliance rules");
    } finally {
      setIsResetting(false);
    }
  }

  if (isLoading) {
    return (
      <section className="panel placeholder-panel">
        <h2>Global Compliance</h2>
        <p>Loading compliance rules...</p>
      </section>
    );
  }

  return (
    <section className="panel compliance-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Compliance</p>
          <h2>Global Compliance Rules</h2>
        </div>
        <p className="panel-copy">
          These rules are prepended into all agent prompts and should stay policy-accurate before running any
          simulation or evaluation.
        </p>
      </div>

      <label className="field">
        <span>Rules Text</span>
        <textarea
          className="compliance-textarea"
          rows={18}
          value={rulesText}
          onChange={(event) => setRulesText(event.target.value)}
        />
      </label>

      <div className="form-actions">
        <button type="button" className="button button-primary" onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Compliance"}
        </button>
        <button
          type="button"
          className="button button-secondary"
          onClick={() => void handleReset()}
          disabled={isResetting}
        >
          {isResetting ? "Resetting..." : "Reset To Default"}
        </button>
      </div>

      {status ? <p className="form-success">{status}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
    </section>
  );
}
