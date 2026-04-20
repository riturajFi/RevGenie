"use client";

import { useState } from "react";

import { BorrowerProfileForm } from "@/components/forms/borrower-profile-form";
import { ConversationLogDashboard } from "@/components/conversation/conversation-log-dashboard";
import { AdminSidebar } from "@/components/navigation/admin-sidebar";
import { ComplianceDashboard } from "@/components/compliance/compliance-dashboard";
import { LenderPolicyDashboard } from "@/components/lender-policy/lender-policy-dashboard";
import { MetaEvalDashboard } from "@/components/meta-eval/meta-eval-dashboard";
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
        {activeTab === "conversation-logs" ? <ConversationLogDashboard /> : null}
        {activeTab === "run-simulation" ? <SimulationRunner /> : null}
        {activeTab === "eval-reports" ? <PerformanceDashboard /> : null}
        {activeTab === "prompt-evolution" ? <PromptEvolutionDashboard /> : null}
        {activeTab === "global-compliance" ? <ComplianceDashboard /> : null}
        {activeTab === "lender-policy" ? <LenderPolicyDashboard /> : null}
        {activeTab === "meta-eval" ? <MetaEvalDashboard /> : null}
      </div>
    </main>
  );
}
