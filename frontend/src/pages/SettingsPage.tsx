import { type FormEvent, useState } from "react";

import { apiGet, apiPost } from "../api/client";
import type { AssignableRole, User, Workspace, WorkspaceMember } from "../types";

export function SettingsPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [createdUser, setCreatedUser] = useState<User | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [lookupEmail, setLookupEmail] = useState("");
  const [lookupUser, setLookupUser] = useState<User | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [role, setRole] = useState<AssignableRole>("member");
  const [memberStatus, setMemberStatus] = useState<string | null>(null);

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    setCreatedUser(null);

    const payload = {
      display_name: displayName.trim(),
      ...(email.trim() ? { email: email.trim().toLowerCase() } : {}),
    };

    try {
      const user = await apiPost<User, typeof payload>("/users", payload);
      setCreatedUser(user);
      setDisplayName("");
      setEmail("");
    } catch {
      setCreateError("Unable to create user");
    }
  }

  async function handleFindUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLookupError(null);
    setLookupUser(null);
    setMemberStatus(null);

    const normalizedEmail = lookupEmail.trim().toLowerCase();
    if (!normalizedEmail) {
      setLookupError("Enter an email to find a user");
      return;
    }

    try {
      const users = await apiGet<User[]>(`/users?email=${encodeURIComponent(normalizedEmail)}`);
      const firstUser = users[0];
      if (!firstUser) {
        setLookupError("No user found for this email");
        return;
      }
      setLookupUser(firstUser);
    } catch {
      setLookupError("Unable to find user");
    }
  }

  async function handleAddMember(user: User) {
    if (!activeWorkspace) {
      setMemberStatus("Select a workspace before adding members");
      return;
    }

    try {
      await apiPost<WorkspaceMember, { user_id: string; role: AssignableRole }>(
        `/workspaces/${activeWorkspace.id}/members`,
        { user_id: user.id, role },
      );
      setMemberStatus(`Added ${user.display_name} to ${activeWorkspace.name} as ${role}`);
    } catch {
      setMemberStatus("Unable to add workspace member");
    }
  }

  return (
    <section className="page-card settings-page">
      <p className="eyebrow">Development settings</p>
      <h2>Settings</h2>
      <p>Create local development users and add existing users to the active workspace.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateUser}>
          <h3>Create development user</h3>
          <label>
            Display name
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              minLength={1}
              required
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button type="submit">Create user</button>
          {createdUser ? <p role="status">Created user {createdUser.display_name}</p> : null}
          {createError ? <p role="alert">{createError}</p> : null}
        </form>

        <form className="settings-panel" onSubmit={handleFindUser}>
          <h3>Add workspace member</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Find user by email
            <input
              type="email"
              value={lookupEmail}
              onChange={(event) => setLookupEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Workspace role
            <select value={role} onChange={(event) => setRole(event.target.value as AssignableRole)}>
              <option value="admin">admin</option>
              <option value="member">member</option>
              <option value="viewer">viewer</option>
            </select>
          </label>
          <button type="submit">Find user</button>
          {lookupError ? <p role="alert">{lookupError}</p> : null}
          {lookupUser ? (
            <div className="user-result">
              <p>
                Found {lookupUser.display_name} {lookupUser.email ? `(${lookupUser.email})` : ""}
              </p>
              <button type="button" onClick={() => void handleAddMember(lookupUser)}>
                Add {lookupUser.display_name} as {role}
              </button>
            </div>
          ) : null}
          {memberStatus ? <p role="status">{memberStatus}</p> : null}
        </form>
      </div>
    </section>
  );
}
