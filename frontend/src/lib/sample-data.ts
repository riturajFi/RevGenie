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
  stage: "ASSESSMENT",
  caseStatus: "OPEN",
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
    id: "global-compliance",
    label: "Global Compliance",
    description: "Set and reset global compliance rules shared by all agents.",
  },
  {
    id: "lender-policy",
    label: "Lender Policy",
    description: "Set and update policy text for each lender.",
  },
  {
    id: "meta-eval",
    label: "Meta Eval",
    description: "Compare experiment runs and metrics changes later.",
  },
];
