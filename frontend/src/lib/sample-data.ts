import { BorrowerTestDefaults } from "@/types/borrower";

export const borrowerCreateDefaults = {
  fullName: "Aarav Sharma",
  phoneNumber: "",
};

export const borrowerTestDefaults: BorrowerTestDefaults = {
  lenderId: "nira",
  workflowId: "wf_demo",
  loanIdMasked: "****4831",
  amountDue: 12921,
  principalOutstanding: 10125,
  dpd: 275,
  caseType: "SETTLEMENT_CANDIDATE",
  stage: "ASSESSMENT",
  caseStatus: "OPEN",
  nextAllowedActions: "OFFER_REDUCED_CLOSURE, OFFER_PAYMENT_PLAN",
};

export const sidebarItems = [
  {
    id: "create-borrower",
    label: "Create Borrower Profile",
    description: "Create a new borrower with backend-aligned testing defaults.",
  },
  {
    id: "run-simulation",
    label: "Run Simulation",
    description: "Run live tester vs collector transcript simulations.",
  },
  {
    id: "eval-reports",
    label: "Eval Reports",
    description: "Review scoring output and saved reports later.",
  },
  {
    id: "prompt-evolution",
    label: "Prompt Evolution",
    description: "Inspect prompt version history and diffs per agent.",
  },
  {
    id: "meta-eval",
    label: "Meta Eval",
    description: "Compare experiment runs and metrics changes later.",
  },
];
