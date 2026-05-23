import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type {
  Account,
  Category,
  ManualTransactionType,
  Transaction,
  TransactionCreatePayload,
  TransferCreatePayload,
  TransferRead,
  Workspace,
} from "../../types";
import { normalizeManualAmount, toApiDateTime } from "../../utils/transactions";

export function TransactionsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState("");
  const [transactionType, setTransactionType] = useState<ManualTransactionType>("expense");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [merchantName, setMerchantName] = useState("");
  const [notes, setNotes] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [transferFromAccountId, setTransferFromAccountId] = useState("");
  const [transferToAccountId, setTransferToAccountId] = useState("");
  const [transferDescription, setTransferDescription] = useState("");
  const [transferAmount, setTransferAmount] = useState("");
  const [transferOccurredAt, setTransferOccurredAt] = useState("");
  const [transferNotes, setTransferNotes] = useState("");
  const [transferStatusMessage, setTransferStatusMessage] = useState<string | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["accounts", activeWorkspace?.id, "transactions-form"],
    queryFn: () => apiGet<Account[]>(`/workspaces/${activeWorkspace?.id}/accounts`),
    enabled: Boolean(activeWorkspace),
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories", activeWorkspace?.id, "transactions-form"],
    queryFn: () => apiGet<Category[]>(`/workspaces/${activeWorkspace?.id}/categories`),
    enabled: Boolean(activeWorkspace),
  });
  const transactionsQuery = useQuery({
    queryKey: ["transactions", activeWorkspace?.id],
    queryFn: () => apiGet<Transaction[]>(`/workspaces/${activeWorkspace?.id}/transactions`),
    enabled: Boolean(activeWorkspace),
  });

  const accountsById = new Map(accountsQuery.data?.map((account) => [account.id, account]));
  const categoriesById = new Map(categoriesQuery.data?.map((category) => [category.id, category]));
  const selectedAccount = accountsById.get(accountId);
  const selectedTransferFromAccount = accountsById.get(transferFromAccountId);

  async function handleCreateTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating transactions");
      return;
    }
    if (!selectedAccount) {
      setStatusMessage("Select an account before creating transactions");
      return;
    }

    setStatusMessage(null);
    const payload: TransactionCreatePayload = {
      account_id: selectedAccount.id,
      type: transactionType,
      occurred_at: toApiDateTime(occurredAt),
      amount: normalizeManualAmount(transactionType, amount),
      currency_code: selectedAccount.currency_code,
      description: description.trim(),
      ...(categoryId ? { category_id: categoryId } : {}),
      ...(merchantName.trim() ? { merchant_name: merchantName.trim() } : {}),
      ...(notes.trim() ? { notes: notes.trim() } : {}),
    };

    try {
      const transaction = await apiPost<Transaction, TransactionCreatePayload>(
        `/workspaces/${activeWorkspace.id}/transactions`,
        payload,
      );
      setStatusMessage(`Created transaction ${transaction.description}`);
      setDescription("");
      setAmount("");
      setOccurredAt("");
      setCategoryId("");
      setMerchantName("");
      setNotes("");
      await queryClient.invalidateQueries({ queryKey: ["transactions", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create transaction");
    }
  }

  async function handleCreateTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setTransferStatusMessage("Select a workspace before creating transfers");
      return;
    }
    if (!selectedTransferFromAccount) {
      setTransferStatusMessage("Select a source account before creating transfers");
      return;
    }

    setTransferStatusMessage(null);
    const payload: TransferCreatePayload = {
      from_account_id: selectedTransferFromAccount.id,
      to_account_id: transferToAccountId,
      occurred_at: toApiDateTime(transferOccurredAt),
      from_amount: transferAmount.trim(),
      from_currency_code: selectedTransferFromAccount.currency_code,
      description: transferDescription.trim(),
      ...(transferNotes.trim() ? { notes: transferNotes.trim() } : {}),
    };

    try {
      const transfer = await apiPost<TransferRead, TransferCreatePayload>(
        `/workspaces/${activeWorkspace.id}/transactions/transfers`,
        payload,
      );
      setTransferStatusMessage(`Created transfer ${transfer.outflow.description}`);
      setTransferFromAccountId("");
      setTransferToAccountId("");
      setTransferDescription("");
      setTransferAmount("");
      setTransferOccurredAt("");
      setTransferNotes("");
      await queryClient.invalidateQueries({ queryKey: ["transactions", activeWorkspace.id] });
    } catch {
      setTransferStatusMessage("Unable to create transfer");
    }
  }

  return (
    <section className="page-card transactions-page">
      <p className="eyebrow">MVP module</p>
      <h2>Transactions</h2>
      <p>Manual expense, income, and adjustment entries for the active workspace.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateTransaction}>
          <h3>Create transaction</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Account
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)} required>
              <option value="">Select account</option>
              {accountsQuery.data?.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} · {account.currency_code}
                </option>
              ))}
            </select>
          </label>
          <label>
            Transaction type
            <select
              value={transactionType}
              onChange={(event) => setTransactionType(event.target.value as ManualTransactionType)}
            >
              <option value="expense">expense</option>
              <option value="income">income</option>
              <option value="adjustment">adjustment</option>
            </select>
          </label>
          <label>
            Description
            <input value={description} onChange={(event) => setDescription(event.target.value)} minLength={1} required />
          </label>
          <label>
            Amount
            <input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} required />
          </label>
          <label>
            Occurred at
            <input
              type="datetime-local"
              value={occurredAt}
              onChange={(event) => setOccurredAt(event.target.value)}
              required
            />
          </label>
          <label>
            Category
            <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
              <option value="">Uncategorized</option>
              {categoriesQuery.data?.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name} · {category.type}
                </option>
              ))}
            </select>
          </label>
          <label>
            Merchant
            <input value={merchantName} onChange={(event) => setMerchantName(event.target.value)} />
          </label>
          <label>
            Notes
            <input value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace || !accountsQuery.data?.length}>Create transaction</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <form className="settings-panel" onSubmit={handleCreateTransfer}>
          <h3>Create transfer</h3>
          <p>Move money between two accounts in the active workspace.</p>
          <label>
            Source account
            <select
              value={transferFromAccountId}
              onChange={(event) => setTransferFromAccountId(event.target.value)}
              required
            >
              <option value="">Select source account</option>
              {accountsQuery.data?.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} · {account.currency_code}
                </option>
              ))}
            </select>
          </label>
          <label>
            Destination account
            <select value={transferToAccountId} onChange={(event) => setTransferToAccountId(event.target.value)} required>
              <option value="">Select destination account</option>
              {accountsQuery.data?.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} · {account.currency_code}
                </option>
              ))}
            </select>
          </label>
          <label>
            Transfer description
            <input
              value={transferDescription}
              onChange={(event) => setTransferDescription(event.target.value)}
              minLength={1}
              required
            />
          </label>
          <label>
            Transfer amount
            <input
              inputMode="decimal"
              value={transferAmount}
              onChange={(event) => setTransferAmount(event.target.value)}
              required
            />
          </label>
          <label>
            Transfer occurred at
            <input
              type="datetime-local"
              value={transferOccurredAt}
              onChange={(event) => setTransferOccurredAt(event.target.value)}
              required
            />
          </label>
          <label>
            Transfer notes
            <input value={transferNotes} onChange={(event) => setTransferNotes(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace || (accountsQuery.data?.length ?? 0) < 2}>Create transfer</button>
          {transferStatusMessage ? <p role="status">{transferStatusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Transaction list</h3>
          {!activeWorkspace ? <p>Select a workspace to load transactions.</p> : null}
          {accountsQuery.isLoading || categoriesQuery.isLoading || transactionsQuery.isLoading ? (
            <p>Loading transactions…</p>
          ) : null}
          {transactionsQuery.isError ? <p role="alert">Unable to load transactions</p> : null}
          {transactionsQuery.data?.length === 0 ? <p>No transactions yet.</p> : null}
          {transactionsQuery.data?.length ? (
            <ul className="entity-list">
              {transactionsQuery.data.map((transaction) => {
                const account = accountsById.get(transaction.account_id);
                const category = transaction.category_id ? categoriesById.get(transaction.category_id) : undefined;
                return (
                  <li key={transaction.id}>
                    <strong>{transaction.description}</strong>
                    <span>
                      {transaction.type} · {transaction.amount} {transaction.currency_code}
                    </span>
                    <span>{[account?.name ?? transaction.account_id, category?.name ?? "Uncategorized"].join(" · ")}</span>
                    {transaction.merchant_name ? <span>Merchant: {transaction.merchant_name}</span> : null}
                    <span>Occurred: {new Date(transaction.occurred_at).toLocaleString()}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}
