"use client";

import { useState } from "react";

import { BorrowerProfileForm } from "@/components/forms/borrower-profile-form";
import { AdminSidebar } from "@/components/navigation/admin-sidebar";
import { PerformanceDashboard } from "@/components/performance/performance-dashboard";
import { PromptEvolutionDashboard } from "@/components/prompt-evolution/prompt-evolution-dashboard";
import { SimulationRunner } from "@/components/simulation/simulation-runner";

export default function AdminDashboardPage() {
  const [activeTab, setActiveTab] = useState("create-borrower");

  return (
    <main className="admin-page">
      <AdminSidebar activeTab={activeTab} onSelectTab={setActiveTab} />
      <div className="admin-content">
        {activeTab === "create-borrower" ? <BorrowerProfileForm /> : null}
        {activeTab === "run-simulation" ? <SimulationRunner /> : null}
        {activeTab === "eval-reports" ? <PerformanceDashboard /> : null}
        {activeTab === "prompt-evolution" ? <PromptEvolutionDashboard /> : null}
        {activeTab === "meta-eval" ? (
          <section className="panel placeholder-panel">
            <h2>Meta Eval</h2>
            <p>This section will run and display meta evaluation next.</p>
          </section>
        ) : null}
      </div>
    </main>
  );
}
