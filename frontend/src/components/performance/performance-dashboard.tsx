"use client";

import { useEffect, useMemo, useState } from "react";

import { getEvalPerformance } from "@/lib/api";
import { EvalPerformanceDataset, EvalPerformancePoint } from "@/types/performance";

import { PerformanceBarChart } from "./performance-bar-chart";

function filterByScenario(points: EvalPerformancePoint[], selectedScenarios: string[]): EvalPerformancePoint[] {
  if (selectedScenarios.length === 0) {
    return points;
  }
  const selected = new Set(selectedScenarios);
  return points.filter((point) => selected.has(point.scenario_id));
}

export function PerformanceDashboard() {
  const [dataset, setDataset] = useState<EvalPerformanceDataset | null>(null);
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadDataset() {
      setIsLoading(true);
      setError(null);
      try {
        const loaded = await getEvalPerformance();
        if (cancelled) return;
        setDataset(loaded);
        setSelectedScenarios(loaded.available_scenarios);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load performance data");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadDataset();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredPoints = useMemo(
    () => filterByScenario(dataset?.points ?? [], selectedScenarios),
    [dataset?.points, selectedScenarios]
  );

  function toggleScenario(scenarioId: string) {
    setSelectedScenarios((current) =>
      current.includes(scenarioId) ? current.filter((item) => item !== scenarioId) : [...current, scenarioId]
    );
  }

  if (isLoading) {
    return (
      <section className="panel placeholder-panel">
        <h2>Performance Graph</h2>
        <p>Loading performance data...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="panel placeholder-panel">
        <h2>Performance Graph</h2>
        <p className="form-error">{error}</p>
      </section>
    );
  }

  return (
    <section className="panel performance-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Evals</p>
          <h2>Prompt Iteration Performance</h2>
        </div>
        <p className="panel-copy">
          Bar chart of evaluation score across prompt iterations. Colors represent scenario. Hover dots for prompt
          versions, metrics used, and run metadata.
        </p>
      </div>

      <div className="scenario-filter-row">
        {(dataset?.available_scenarios ?? []).map((scenarioId) => (
          <label key={scenarioId} className="checkbox-inline">
            <input
              type="checkbox"
              checked={selectedScenarios.includes(scenarioId)}
              onChange={() => toggleScenario(scenarioId)}
            />
            <span>{scenarioId}</span>
          </label>
        ))}
      </div>

      <PerformanceBarChart points={filteredPoints} />
    </section>
  );
}
