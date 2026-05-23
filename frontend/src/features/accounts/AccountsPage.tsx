import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type { Account, AccountCreatePayload, AccountType, Workspace } from "../../types";

export function AccountsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState<AccountType>("bank_card");
  const [currencyCode, setCurrencyCode] = useState(activeWorkspace?.base_currency_code ?? "");
  const [openingBalance, setOpeningBalance] = useState("");
  const [institutionName, setInstitutionName] = useState("");
  const [maskedNumber, setMaskedNumber] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["accounts", activeWorkspace?.id],
    queryFn: () => apiGet<Account[]>(`/workspaces/${activeWorkspace?.id}/accounts`),
    enabled: Boolean(activeWorkspace),
  });

  async function handleCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating accounts");
      return;
    }

    setStatusMessage(null);
    const payload: AccountCreatePayload = {
      name: name.trim(),
      type: accountType,
      currency_code: currencyCode.trim().toUpperCase(),
      opening_balance: openingBalance.trim() || "0",
      ...(institutionName.trim() ? { institution_name: institutionName.trim() } : {}),
      ...(maskedNumber.trim() ? { masked_number: maskedNumber.trim() } : {}),
    };

    try {
      const account = await apiPost<Account, AccountCreatePayload>(
        `/workspaces/${activeWorkspace.id}/accounts`,
        payload,
      );
      setStatusMessage(`Created account ${account.name}`);
      setName("");
      setAccountType("bank_card");
      setCurrencyCode(activeWorkspace.base_currency_code);
      setOpeningBalance("");
      setInstitutionName("");
      setMaskedNumber("");
      await queryClient.invalidateQueries({ queryKey: ["accounts", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create account");
    }
  }

  return (
    <section className="page-card accounts-page">
      <p className="eyebrow">MVP module</p>
      <h2>Accounts</h2>
      <p>Cards, cash wallets, bank accounts, bonus balances, crypto, and investments.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateAccount}>
          <h3>Create account</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Account name
            <input value={name} onChange={(event) => setName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Account type
            <select value={accountType} onChange={(event) => setAccountType(event.target.value as AccountType)}>
              <option value="bank_card">bank_card</option>
              <option value="cash">cash</option>
              <option value="bank_account">bank_account</option>
              <option value="bonus">bonus</option>
              <option value="investment">investment</option>
              <option value="crypto">crypto</option>
              <option value="other">other</option>
            </select>
          </label>
          <label>
            Currency
            <input
              value={currencyCode}
              onChange={(event) => setCurrencyCode(event.target.value)}
              placeholder={activeWorkspace?.base_currency_code ?? "RUB"}
              minLength={3}
              maxLength={3}
              required
            />
          </label>
          <label>
            Opening balance
            <input
              inputMode="decimal"
              value={openingBalance}
              onChange={(event) => setOpeningBalance(event.target.value)}
            />
          </label>
          <label>
            Institution name
            <input value={institutionName} onChange={(event) => setInstitutionName(event.target.value)} />
          </label>
          <label>
            Masked number
            <input value={maskedNumber} onChange={(event) => setMaskedNumber(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace}>Create account</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Account list</h3>
          {!activeWorkspace ? <p>Select a workspace to load accounts.</p> : null}
          {accountsQuery.isLoading ? <p>Loading accounts…</p> : null}
          {accountsQuery.isError ? <p role="alert">Unable to load accounts</p> : null}
          {accountsQuery.data?.length === 0 ? <p>No accounts yet.</p> : null}
          {accountsQuery.data?.length ? (
            <ul className="entity-list">
              {accountsQuery.data.map((account) => (
                <li key={account.id}>
                  <strong>{account.name}</strong>
                  <span>
                    {account.type} · {account.currency_code}
                  </span>
                  {account.institution_name || account.masked_number ? (
                    <span>
                      {[account.institution_name, account.masked_number].filter(Boolean).join(" · ")}
                    </span>
                  ) : null}
                  <span>Opening balance: {account.opening_balance}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}
