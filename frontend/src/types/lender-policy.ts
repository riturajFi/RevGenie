export type LenderPolicyRecord = {
  lender_id: string;
  policy: string;
};

export type UpsertLenderPolicyResult = {
  record: LenderPolicyRecord;
  mode: "created" | "updated";
};
