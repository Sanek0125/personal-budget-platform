import { type ChangeEvent, type FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiGet, apiPost, apiPostForm } from "../../api/client";
import type { Account, CsvImportUploadPayload, ImportBatch, ImportConfirmResult, ImportRow, User, Workspace } from "../../types";

type ImportParserName = "generic_csv" | "freedom";

function readFileAsText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    return file.text();
  }

  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result ?? "")));
    reader.addEventListener("error", () => reject(reader.error ?? new Error("Unable to read file")));
    reader.readAsText(file);
  });
}

export function ImportsPage({ activeWorkspace, currentUser }: { activeWorkspace?: Workspace; currentUser: User }) {
  const [accountId, setAccountId] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [parserName, setParserName] = useState<ImportParserName>("generic_csv");
  const [originalFilename, setOriginalFilename] = useState("");
  const [csvContent, setCsvContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentBatch, setCurrentBatch] = useState<ImportBatch | null>(null);
  const [importRows, setImportRows] = useState<ImportRow[]>([]);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["accounts", activeWorkspace?.id, "imports-page"],
    queryFn: () => apiGet<Account[]>(`/workspaces/${activeWorkspace?.id}/accounts`),
    enabled: Boolean(activeWorkspace),
  });

  async function handleStatementFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      setSelectedFile(file);
      setOriginalFilename(file.name);
      if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
        setCsvContent("");
        setStatusMessage(`Selected file ${file.name}`);
        return;
      }
      const content = await readFileAsText(file);
      setCsvContent(content);
      setStatusMessage(`Selected file ${file.name}`);
    } catch {
      setStatusMessage("Unable to read selected file");
    }
  }

  async function handleUploadImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before uploading imports");
      return;
    }
    if (!accountId) {
      setStatusMessage("Select an account before uploading imports");
      return;
    }

    setStatusMessage(null);
    const trimmedSourceName = sourceName.trim();
    const isRawPdfUpload = Boolean(selectedFile && originalFilename.trim().toLowerCase().endsWith(".pdf"));

    try {
      let batch: ImportBatch;
      if (isRawPdfUpload && selectedFile) {
        const formData = new FormData();
        formData.append("user_id", currentUser.id);
        formData.append("account_id", accountId);
        formData.append("parser_name", parserName);
        const resolvedSourceName = trimmedSourceName || (parserName === "freedom" ? "Freedom Bank" : "");
        if (resolvedSourceName) {
          formData.append("source_name", resolvedSourceName);
        }
        formData.append("file", selectedFile);
        batch = await apiPostForm<ImportBatch>(`/workspaces/${activeWorkspace.id}/imports/upload-file`, formData);
      } else {
        const payload: CsvImportUploadPayload = {
          user_id: currentUser.id,
          account_id: accountId,
          original_filename: originalFilename.trim(),
          content: csvContent.trim(),
          ...(trimmedSourceName ? { source_name: trimmedSourceName } : parserName === "freedom" ? { source_name: "Freedom Bank" } : {}),
          ...(parserName === "freedom"
            ? { parser_name: "freedom" }
            : {
                parser_name: "generic_csv",
                column_mapping: {
                  occurred_at: "Date",
                  amount: "Amount",
                  currency_code: "Currency",
                  description: "Description",
                },
              }),
        };
        batch = await apiPost<ImportBatch, CsvImportUploadPayload>(
          `/workspaces/${activeWorkspace.id}/imports/upload`,
          payload,
        );
      }
      const rows = await apiGet<ImportRow[]>(`/workspaces/${activeWorkspace.id}/imports/${batch.id}/rows`);
      setCurrentBatch(batch);
      setImportRows(rows);
      setStatusMessage(`Uploaded import ${batch.original_filename}`);
    } catch {
      setStatusMessage("Unable to upload import");
    }
  }

  async function handleConfirmImport() {
    if (!activeWorkspace || !currentBatch) {
      setStatusMessage("Upload an import before confirming it");
      return;
    }

    try {
      const result = await apiPost<ImportConfirmResult, Record<string, never>>(
        `/workspaces/${activeWorkspace.id}/imports/${currentBatch.id}/confirm`,
        {},
      );
      setStatusMessage(
        `Confirmed import: ${result.imported_count} imported, ${result.duplicate_count} duplicates, ${result.error_count} errors`,
      );
    } catch {
      setStatusMessage("Unable to confirm import");
    }
  }

  return (
    <section className="page-card imports-page">
      <p className="eyebrow">MVP module</p>
      <h2>Imports</h2>
      <p>Upload CSV statements or raw bank PDF statements, preview normalized rows, and confirm them into transactions.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleUploadImport}>
          <h3>Upload CSV import</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Target account
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
            Parser
            <select value={parserName} onChange={(event) => setParserName(event.target.value as ImportParserName)}>
              <option value="generic_csv">Generic CSV</option>
              <option value="freedom">Freedom Bank</option>
            </select>
          </label>
          <label>
            Source name
            <input value={sourceName} onChange={(event) => setSourceName(event.target.value)} placeholder={parserName === "freedom" ? "Freedom Bank" : undefined} />
          </label>
          <label>
            Statement file
            <input accept=".csv,.txt,.pdf,text/csv,text/plain,application/pdf" type="file" onChange={(event) => void handleStatementFileChange(event)} />
          </label>
          <label>
            Original filename
            <input
              value={originalFilename}
              onChange={(event) => {
                setOriginalFilename(event.target.value);
              }}
              required
            />
          </label>
          <label>
            CSV content / extracted PDF text preview
            <textarea
              value={csvContent}
              onChange={(event) => setCsvContent(event.target.value)}
              placeholder="Date,Amount,Currency,Description\n2026-05-21,-12.34,RUB,Lunch"
              rows={8}
              required={!selectedFile?.name.toLowerCase().endsWith(".pdf")}
            />
          </label>
          <p>
            Expected columns: <strong>{parserName === "freedom" ? "Freedom statement columns" : "Date, Amount, Currency, Description"}</strong>
          </p>
          <button type="submit" disabled={!activeWorkspace || !accountsQuery.data?.length}>Upload import</button>
          {currentBatch ? (
            <button type="button" onClick={() => void handleConfirmImport()}>
              Confirm import
            </button>
          ) : null}
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Import preview</h3>
          {!activeWorkspace ? <p>Select a workspace to upload imports.</p> : null}
          {accountsQuery.isLoading ? <p>Loading accounts…</p> : null}
          {accountsQuery.isError ? <p role="alert">Unable to load accounts</p> : null}
          {currentBatch ? (
            <p>
              Batch {currentBatch.status} · {currentBatch.total_rows} rows · {currentBatch.original_filename}
            </p>
          ) : null}
          {importRows.length === 0 ? <p>No import rows previewed yet.</p> : null}
          {importRows.length ? (
            <ul className="entity-list">
              {importRows.map((row) => (
                <li key={row.id}>
                  <strong>{row.normalized_data?.description ?? `Row ${row.row_number}`}</strong>
                  <span>
                    {row.normalized_data?.type ?? "unknown"} · {row.normalized_data?.amount ?? "?"}{" "}
                    {row.normalized_data?.currency_code ?? ""} · {row.status}
                  </span>
                  <span>Row {row.row_number}</span>
                  {row.error_message ? <span>Error: {row.error_message}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}
