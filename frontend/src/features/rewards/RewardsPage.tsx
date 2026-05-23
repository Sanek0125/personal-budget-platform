import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type {
  RewardEvent,
  RewardEventCreatePayload,
  RewardEventStatus,
  RewardEventType,
  RewardKind,
  RewardProgram,
  RewardProgramCreatePayload,
  RewardProgramType,
  Workspace,
} from "../../types";
import { toApiDateTime } from "../../utils/transactions";

export function RewardsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [programName, setProgramName] = useState("");
  const [programType, setProgramType] = useState<RewardProgramType>("cashback");
  const [programCurrency, setProgramCurrency] = useState(activeWorkspace?.base_currency_code ?? "");
  const [issuerName, setIssuerName] = useState("");
  const [programNotes, setProgramNotes] = useState("");
  const [eventProgramId, setEventProgramId] = useState("");
  const [eventType, setEventType] = useState<RewardEventType>("earned");
  const [eventStatus, setEventStatus] = useState<RewardEventStatus>("posted");
  const [eventAmount, setEventAmount] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [eventDescription, setEventDescription] = useState("");
  const [eventNotes, setEventNotes] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const programsQuery = useQuery({
    queryKey: ["reward-programs", activeWorkspace?.id],
    queryFn: () => apiGet<RewardProgram[]>(`/workspaces/${activeWorkspace?.id}/rewards/programs`),
    enabled: Boolean(activeWorkspace),
  });
  const eventsQuery = useQuery({
    queryKey: ["reward-events", activeWorkspace?.id],
    queryFn: () => apiGet<RewardEvent[]>(`/workspaces/${activeWorkspace?.id}/rewards/events`),
    enabled: Boolean(activeWorkspace),
  });

  const selectedProgram = programsQuery.data?.find((program) => program.id === eventProgramId) ?? programsQuery.data?.[0];
  const selectedRewardKind: RewardKind = selectedProgram?.program_type ?? "cashback";

  async function handleCreateProgram(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating reward programs");
      return;
    }

    setStatusMessage(null);
    const payload: RewardProgramCreatePayload = {
      name: programName.trim(),
      program_type: programType,
      ...(programType === "cashback" ? { currency_code: programCurrency.trim().toUpperCase() } : {}),
      ...(issuerName.trim() ? { issuer_name: issuerName.trim() } : {}),
      is_active: true,
      ...(programNotes.trim() ? { notes: programNotes.trim() } : {}),
    };

    try {
      const program = await apiPost<RewardProgram, RewardProgramCreatePayload>(
        `/workspaces/${activeWorkspace.id}/rewards/programs`,
        payload,
      );
      setStatusMessage(`Created reward program ${program.name}`);
      setProgramName("");
      setProgramCurrency(activeWorkspace.base_currency_code);
      setIssuerName("");
      setProgramNotes("");
      await queryClient.invalidateQueries({ queryKey: ["reward-programs", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create reward program");
    }
  }

  async function handleCreateEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating reward events");
      return;
    }
    if (!selectedProgram) {
      setStatusMessage("Create a reward program before adding events");
      return;
    }

    setStatusMessage(null);
    const payload: RewardEventCreatePayload = {
      program_id: selectedProgram.id,
      event_type: eventType,
      status: eventStatus,
      reward_kind: selectedRewardKind,
      amount: eventAmount.trim(),
      ...(selectedProgram.currency_code ? { currency_code: selectedProgram.currency_code } : {}),
      occurred_at: toApiDateTime(occurredAt),
      ...(eventDescription.trim() ? { description: eventDescription.trim() } : {}),
      ...(eventNotes.trim() ? { notes: eventNotes.trim() } : {}),
    };

    try {
      const rewardEvent = await apiPost<RewardEvent, RewardEventCreatePayload>(
        `/workspaces/${activeWorkspace.id}/rewards/events`,
        payload,
      );
      setStatusMessage(`Created reward event ${rewardEvent.description}`);
      setEventAmount("");
      setOccurredAt("");
      setEventDescription("");
      setEventNotes("");
      await queryClient.invalidateQueries({ queryKey: ["reward-events", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create reward event");
    }
  }

  return (
    <section className="page-card rewards-page">
      <p className="eyebrow">MVP module</p>
      <h2>Rewards</h2>
      <p>Track reward programs and manually posted cashback, points, and miles events.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateProgram}>
          <h3>Create reward program</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Program name
            <input value={programName} onChange={(event) => setProgramName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Program type
            <select
              value={programType}
              onChange={(event) => {
                const nextType = event.target.value as RewardProgramType;
                setProgramType(nextType);
                if (nextType !== "cashback") {
                  setProgramCurrency("");
                } else if (!programCurrency) {
                  setProgramCurrency(activeWorkspace?.base_currency_code ?? "");
                }
              }}
            >
              <option value="cashback">cashback</option>
              <option value="points">points</option>
              <option value="miles">miles</option>
            </select>
          </label>
          <label>
            Reward currency
            <input
              value={programCurrency}
              onChange={(event) => setProgramCurrency(event.target.value)}
              placeholder={activeWorkspace?.base_currency_code ?? "RUB"}
              minLength={programType === "cashback" ? 3 : undefined}
              maxLength={3}
              required={programType === "cashback"}
              disabled={programType !== "cashback"}
            />
          </label>
          <label>
            Issuer name
            <input value={issuerName} onChange={(event) => setIssuerName(event.target.value)} />
          </label>
          <label>
            Program notes
            <textarea value={programNotes} onChange={(event) => setProgramNotes(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace}>Create reward program</button>
        </form>

        <form className="settings-panel" onSubmit={handleCreateEvent}>
          <h3>Create reward event</h3>
          <label>
            Event program
            <select value={selectedProgram?.id ?? ""} onChange={(event) => setEventProgramId(event.target.value)} required>
              <option value="" disabled>
                Select program
              </option>
              {programsQuery.data?.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Event type
            <select value={eventType} onChange={(event) => setEventType(event.target.value as RewardEventType)}>
              <option value="earned">earned</option>
              <option value="redeemed">redeemed</option>
              <option value="adjusted">adjusted</option>
              <option value="expired">expired</option>
            </select>
          </label>
          <label>
            Event status
            <select value={eventStatus} onChange={(event) => setEventStatus(event.target.value as RewardEventStatus)}>
              <option value="posted">posted</option>
              <option value="expected">expected</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
          <label>
            Reward amount
            <input inputMode="decimal" value={eventAmount} onChange={(event) => setEventAmount(event.target.value)} required />
          </label>
          <label>
            Occurred at
            <input type="datetime-local" value={occurredAt} onChange={(event) => setOccurredAt(event.target.value)} required />
          </label>
          <label>
            Reward description
            <input value={eventDescription} onChange={(event) => setEventDescription(event.target.value)} />
          </label>
          <label>
            Reward notes
            <textarea value={eventNotes} onChange={(event) => setEventNotes(event.target.value)} />
          </label>
          <button type="submit" disabled={!activeWorkspace || !selectedProgram}>Create reward event</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>
      </div>

      <div className="settings-grid">
        <div className="settings-panel">
          <h3>Reward programs</h3>
          {!activeWorkspace ? <p>Select a workspace to load rewards.</p> : null}
          {programsQuery.isLoading ? <p>Loading reward programs…</p> : null}
          {programsQuery.isError ? <p role="alert">Unable to load reward programs</p> : null}
          {programsQuery.data?.length === 0 ? <p>No reward programs yet.</p> : null}
          {programsQuery.data?.length ? (
            <ul className="entity-list">
              {programsQuery.data.map((program) => (
                <li key={program.id}>
                  <strong>{program.name}</strong>
                  <span>
                    {program.program_type} · {program.currency_code ?? "unitless"} · {program.is_active ? "active" : "inactive"}
                  </span>
                  {program.issuer_name ? <span>Issuer: {program.issuer_name}</span> : null}
                  {program.notes ? <span>Notes: {program.notes}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="settings-panel">
          <h3>Reward events</h3>
          {eventsQuery.isLoading ? <p>Loading reward events…</p> : null}
          {eventsQuery.isError ? <p role="alert">Unable to load reward events</p> : null}
          {eventsQuery.data?.length === 0 ? <p>No reward events yet.</p> : null}
          {eventsQuery.data?.length ? (
            <ul className="entity-list">
              {eventsQuery.data.map((rewardEvent) => (
                <li key={rewardEvent.id}>
                  <strong>{rewardEvent.description}</strong>
                  <span>
                    {rewardEvent.event_type} · {rewardEvent.status} · {rewardEvent.amount} {rewardEvent.currency_code ?? rewardEvent.reward_kind}
                  </span>
                  <span>Program: {rewardEvent.program_id}</span>
                  <span>Occurred: {rewardEvent.occurred_at}</span>
                  {rewardEvent.notes ? <span>Notes: {rewardEvent.notes}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}
