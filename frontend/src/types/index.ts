export type WorkspaceKind = "personal" | "family" | "trip" | "other";

export type Workspace = {
  id: string;
  name: string;
  kind: WorkspaceKind;
  base_currency_code: string;
  owner_user_id: string;
};

export type WorkspaceCreatePayload = {
  name: string;
  kind: WorkspaceKind;
  base_currency_code: string;
};

export type User = {
  id: string;
  email: string | null;
  display_name: string;
  telegram_id: number | null;
  is_active: boolean;
};

export type AuthToken = {
  access_token: string;
  token_type: "bearer";
  user: User;
};

export type WorkspaceMember = {
  id: string;
  workspace_id: string;
  user_id: string;
  role: "owner" | "admin" | "member" | "viewer";
};

export type AccountType = "bank_card" | "cash" | "bank_account" | "bonus" | "investment" | "crypto" | "other";

export type Account = {
  id: string;
  workspace_id: string;
  owner_user_id: string | null;
  name: string;
  type: AccountType;
  currency_code: string;
  institution_name: string | null;
  masked_number: string | null;
  opening_balance: string;
  is_active: boolean;
};

export type AccountCreatePayload = {
  name: string;
  type: AccountType;
  currency_code: string;
  opening_balance: string;
  institution_name?: string;
  masked_number?: string;
};

export type CategoryType = "expense" | "income" | "transfer" | "mixed";

export type Category = {
  id: string;
  workspace_id: string;
  parent_id: string | null;
  name: string;
  type: CategoryType;
  color: string | null;
  icon: string | null;
  sort_order: number;
  is_system: boolean;
};

export type CategoryCreatePayload = {
  name: string;
  type: CategoryType;
  color?: string;
  icon?: string;
  sort_order: number;
};

export type CategoryRuleOperator = "contains" | "equals" | "starts_with" | "regex" | "amount_between";
export type CategoryRuleMatchField = "description" | "merchant_name" | "merchant_raw";

export type CategoryRule = {
  id: string;
  workspace_id: string;
  category_id: string;
  name: string;
  operator: CategoryRuleOperator;
  match_field: CategoryRuleMatchField;
  pattern: string | null;
  amount_min: string | null;
  amount_max: string | null;
  priority: number;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type CategoryRuleCreatePayload = {
  name: string;
  category_id: string;
  operator: CategoryRuleOperator;
  match_field: CategoryRuleMatchField;
  pattern?: string;
  amount_min?: string;
  amount_max?: string;
  priority: number;
  is_active: boolean;
};

export type CategoryRuleApplyResult = {
  evaluated_count: number;
  categorized_count: number;
  transaction_ids: string[];
};

export type TransactionType = "expense" | "income" | "adjustment" | "transfer";
export type ManualTransactionType = "expense" | "income" | "adjustment";

export type TransactionSplit = {
  id: string;
  transaction_id: string;
  category_id: string | null;
  amount: string;
  currency_code: string;
  description: string | null;
  sort_order: number;
  created_at: string | null;
  updated_at: string | null;
};

export type Transaction = {
  id: string;
  workspace_id: string;
  account_id: string;
  user_id: string | null;
  type: TransactionType;
  status: "posted" | "pending" | "deleted" | "duplicate" | "ignored";
  occurred_at: string;
  booked_at: string | null;
  amount: string;
  currency_code: string;
  original_amount: string | null;
  original_currency_code: string | null;
  base_amount: string | null;
  base_currency_code: string | null;
  exchange_rate_id: string | null;
  exchange_rate: string | null;
  description: string;
  merchant_name: string | null;
  merchant_raw: string | null;
  category_id: string | null;
  category_confidence: string | null;
  categorized_by: string | null;
  notes: string | null;
  source: string;
  external_id: string | null;
  fingerprint: string;
  created_at: string | null;
  updated_at: string | null;
  deleted_at: string | null;
  splits: TransactionSplit[];
};

export type TransactionSplitCreatePayload = {
  category_id: string;
  amount: string;
  currency_code: string;
  description?: string;
  sort_order: number;
};

export type TransactionCreatePayload = {
  account_id: string;
  type: ManualTransactionType;
  occurred_at: string;
  amount: string;
  currency_code: string;
  description: string;
  category_id?: string;
  merchant_name?: string;
  notes?: string;
  splits?: TransactionSplitCreatePayload[];
};

export type TransferCreatePayload = {
  from_account_id: string;
  to_account_id: string;
  occurred_at: string;
  from_amount: string;
  from_currency_code: string;
  to_amount?: string;
  to_currency_code?: string;
  exchange_rate?: string;
  description: string;
  notes?: string;
};

export type TransferRead = {
  outflow: Transaction;
  inflow: Transaction;
  link_id: string;
};

export type Budget = {
  id: string;
  workspace_id: string;
  name: string;
  period_type: "monthly";
  period_start: string;
  period_end: string;
  currency_code: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type BudgetCreatePayload = {
  name: string;
  period_type: "monthly";
  period_start: string;
  period_end: string;
  currency_code: string;
  is_active: boolean;
};

export type BudgetLimit = {
  id: string;
  budget_id: string;
  category_id: string;
  amount: string;
  currency_code: string;
  rollover: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type BudgetLimitCreatePayload = {
  category_id: string;
  amount: string;
  currency_code: string;
  rollover: boolean;
};

export type BudgetLimitProgress = {
  category_id: string;
  limit_amount: string;
  spent_amount: string;
  remaining_amount: string;
  percent_used: string;
  currency_code: string;
};

export type BudgetProgress = {
  budget_id: string;
  period_start: string;
  period_end: string;
  currency_code: string;
  total_limit: string;
  total_spent: string;
  total_remaining: string;
  limits: BudgetLimitProgress[];
};

export type ImportBatch = {
  id: string;
  workspace_id: string;
  user_id: string;
  account_id: string | null;
  file_id: string | null;
  source_type: string;
  source_name: string | null;
  original_filename: string;
  file_hash: string;
  file_size: number | null;
  status: "uploaded" | "parsed" | "processed" | "failed" | "partially_processed";
  total_rows: number;
  imported_count: number;
  duplicate_count: number;
  error_count: number;
  parser_version: string | null;
  uploaded_at: string | null;
  processed_at: string | null;
};

export type ImportRow = {
  id: string;
  import_batch_id: string;
  workspace_id: string;
  row_number: number;
  raw_data: Record<string, unknown>;
  normalized_data: {
    type?: string;
    occurred_at?: string;
    amount?: string;
    currency_code?: string;
    description?: string;
  } | null;
  raw_hash: string;
  normalized_hash: string | null;
  status: "pending" | "imported" | "duplicate" | "possible_duplicate" | "ignored" | "error";
  error_message: string | null;
  transaction_id: string | null;
  created_at: string | null;
};

export type CsvImportUploadPayload = {
  user_id: string;
  account_id: string;
  original_filename: string;
  content: string;
  source_name?: string;
  parser_name?: "generic_csv" | "freedom";
  column_mapping?: {
    occurred_at: string;
    amount: string;
    currency_code: string;
    description: string;
    booked_at?: string;
    merchant_name?: string;
    merchant_raw?: string;
    external_id?: string;
    category_id?: string;
  };
};

export type ImportConfirmResult = {
  import_batch_id: string;
  imported_count: number;
  duplicate_count: number;
  error_count: number;
  transaction_ids: string[];
};

export type DebtDirection = "they_owe_me" | "i_owe_them";
export type DebtStatus = "open" | "partially_paid" | "paid" | "cancelled";

export type DebtPayment = {
  id: string;
  debt_id: string;
  amount: string;
  currency_code: string;
  paid_at: string | null;
  notes: string | null;
  transaction_id: string | null;
  created_at: string | null;
};

export type Debt = {
  id: string;
  workspace_id: string;
  contact_id: string;
  direction: DebtDirection;
  status: DebtStatus;
  principal_amount: string;
  currency_code: string;
  description: string;
  due_date: string | null;
  source_transaction_id: string | null;
  opened_at: string | null;
  closed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  payments: DebtPayment[];
};

export type DebtCreatePayload = {
  contact_name: string;
  direction: DebtDirection;
  principal_amount: string;
  currency_code: string;
  description: string;
  due_date?: string;
};

export type DebtSummaryTotal = {
  direction: DebtDirection;
  currency_code: string;
  principal_amount: string;
  paid_amount: string;
  remaining_amount: string;
};

export type DebtSummary = {
  workspace_id: string | null;
  totals: DebtSummaryTotal[];
};

export type RewardProgramType = "cashback" | "points" | "miles";
export type RewardEventType = "earned" | "redeemed" | "adjusted" | "expired";
export type RewardEventStatus = "expected" | "posted" | "cancelled";
export type RewardKind = "cashback" | "points" | "miles";

export type RewardProgram = {
  id: string;
  workspace_id: string;
  name: string;
  program_type: RewardProgramType;
  currency_code: string | null;
  issuer_name: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type RewardProgramCreatePayload = {
  name: string;
  program_type: RewardProgramType;
  currency_code?: string;
  issuer_name?: string;
  is_active: boolean;
  notes?: string;
};

export type RewardEvent = {
  id: string;
  workspace_id: string;
  program_id: string;
  cashback_rule_id: string | null;
  source_transaction_id: string | null;
  reward_transaction_id: string | null;
  event_type: RewardEventType;
  status: RewardEventStatus;
  reward_kind: RewardKind;
  amount: string;
  currency_code: string | null;
  occurred_at: string;
  description: string;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type RewardEventCreatePayload = {
  program_id: string;
  event_type: RewardEventType;
  status: RewardEventStatus;
  reward_kind: RewardKind;
  amount: string;
  currency_code?: string;
  occurred_at: string;
  description?: string;
  notes?: string;
};

export type AssignableRole = "admin" | "member" | "viewer";
