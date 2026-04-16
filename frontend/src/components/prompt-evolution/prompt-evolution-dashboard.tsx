"use client";

import { useEffect, useMemo, useState } from "react";

import { getPromptEvolution } from "@/lib/api";
import { PromptDiffLine, PromptEvolutionResponse, PromptVersionEvolution } from "@/types/prompt-evolution";

type AgentOption = {
  id: string;
  label: string;
};

const AGENTS: AgentOption[] = [
  { id: "agent_1", label: "Agent 1" },
  { id: "agent_2", label: "Agent 2" },
  { id: "agent_3", label: "Agent 3" },
];

function DiffView({ lines }: { lines: PromptDiffLine[] }) {
  if (lines.length === 0) {
    return <p className="prompt-evolution-empty">No diff available for baseline version.</p>;
  }

  return (
    <pre className="prompt-diff-view">
      {lines.map((line, index) => {
        const prefix = line.line_type === "add" ? "+" : line.line_type === "remove" ? "-" : " ";
        return (
          <div key={`${line.line_type}-${index}`} className={`diff-line diff-line-${line.line_type}`}>
            <span className="diff-prefix">{prefix}</span>
            <span className="diff-text">{line.text}</span>
          </div>
        );
      })}
    </pre>
  );
}

export function PromptEvolutionDashboard() {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(AGENTS[0].id);
  const [dataByAgent, setDataByAgent] = useState<Record<string, PromptEvolutionResponse>>({});
  const [selectedVersionByAgent, setSelectedVersionByAgent] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getPromptEvolution(selectedAgentId);
        if (cancelled) return;
        setDataByAgent((current) => ({ ...current, [selectedAgentId]: data }));
        setSelectedVersionByAgent((current) => ({
          ...current,
          [selectedAgentId]: current[selectedAgentId] ?? data.active_version_id,
        }));
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load prompt evolution");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    if (!dataByAgent[selectedAgentId]) {
      void load();
    }
    return () => {
      cancelled = true;
    };
  }, [selectedAgentId, dataByAgent]);

  const selectedData = dataByAgent[selectedAgentId] ?? null;
  const selectedVersionId = selectedVersionByAgent[selectedAgentId] ?? selectedData?.active_version_id ?? null;
  const selectedVersion = useMemo(() => {
    if (!selectedData || !selectedVersionId) return null;
    return selectedData.versions.find((version) => version.version_id === selectedVersionId) ?? null;
  }, [selectedData, selectedVersionId]);

  function renderVersionChain(versions: PromptVersionEvolution[]) {
    return (
      <div className="version-chain">
        {versions.map((version, index) => (
          <div key={version.version_id} className="version-chain-node">
            <button
              type="button"
              className={selectedVersionId === version.version_id ? "version-pill version-pill-active" : "version-pill"}
              onClick={() =>
                setSelectedVersionByAgent((current) => ({
                  ...current,
                  [selectedAgentId]: version.version_id,
                }))
              }
            >
              {version.version_id}
            </button>
            {index < versions.length - 1 ? <span className="version-arrow">-></span> : null}
          </div>
        ))}
      </div>
    );
  }

  return (
    <section className="panel prompt-evolution-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Prompts</p>
          <h2>Agent Prompt Evolution</h2>
        </div>
        <p className="panel-copy">
          Version-chain and GitHub-style diff view for each agent prompt. Select a version to inspect changes against
          its previous version.
        </p>
      </div>

      <div className="prompt-evolution-layout">
        <aside className="agent-selector">
          {AGENTS.map((agent) => (
            <button
              key={agent.id}
              type="button"
              className={selectedAgentId === agent.id ? "agent-button agent-button-active" : "agent-button"}
              onClick={() => setSelectedAgentId(agent.id)}
            >
              {agent.label}
            </button>
          ))}
        </aside>

        <div className="prompt-evolution-content">
          {isLoading && !selectedData ? <p>Loading prompt evolution...</p> : null}
          {error ? <p className="form-error">{error}</p> : null}

          {selectedData ? (
            <>
              {renderVersionChain(selectedData.versions)}
              {selectedVersion ? (
                <article className="prompt-version-detail">
                  <header>
                    <h3>
                      {selectedVersion.version_id}
                      {selectedVersion.previous_version_id
                        ? ` vs ${selectedVersion.previous_version_id}`
                        : " (baseline)"}
                    </h3>
                    <span>{new Date(selectedVersion.created_at).toLocaleString()}</span>
                  </header>
                  <p>
                    Active version: <strong>{selectedData.active_version_id}</strong> | Lines:{" "}
                    <strong>{selectedVersion.prompt_line_count}</strong>
                  </p>
                  <p>
                    Diff summary:{" "}
                    <strong>{selectedVersion.diff_summary ?? "No diff summary recorded for this version."}</strong>
                  </p>
                  <DiffView lines={selectedVersion.diff_lines} />
                </article>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
