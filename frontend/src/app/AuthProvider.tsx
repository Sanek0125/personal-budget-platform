import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import { apiGet, apiPost, clearAccessToken, readStoredAccessToken, storeAccessToken } from "../api/client";
import type { AuthToken, User } from "../types";
import { AuthContext, type AuthContextValue } from "./authContext";

type AuthState =
  | { status: "checking"; user: null; error: null }
  | { status: "unauthenticated"; user: null; error: string | null }
  | { status: "authenticated"; user: User; error: null };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>(() =>
    readStoredAccessToken()
      ? { status: "checking", user: null, error: null }
      : { status: "unauthenticated", user: null, error: null },
  );

  useEffect(() => {
    const accessToken = readStoredAccessToken();
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    apiGet<User>("/auth/me", { accessToken })
      .then((user) => {
        if (!cancelled) {
          setAuthState({ status: "authenticated", user, error: null });
        }
      })
      .catch(() => {
        clearAccessToken();
        if (!cancelled) {
          setAuthState({ status: "unauthenticated", user: null, error: "Session expired. Please sign in again." });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function authenticate(endpoint: "/auth/login" | "/auth/register", payload: Record<string, string>) {
    const response = await apiPost<AuthToken, Record<string, string>>(endpoint, payload, { accessToken: null });
    storeAccessToken(response.access_token);
    setAuthState({ status: "authenticated", user: response.user, error: null });
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser: authState.user,
      login: async (email, password) => {
        await authenticate("/auth/login", { email: email.trim().toLowerCase(), password });
      },
      register: async (email, password, displayName) => {
        await authenticate("/auth/register", {
          email: email.trim().toLowerCase(),
          password,
          display_name: displayName.trim(),
        });
      },
      logout: async () => {
        try {
          await apiPost<undefined, Record<string, never>>("/auth/logout", {});
        } catch {
          // Local logout should still clear the stale client token if the server is unreachable.
        }
        clearAccessToken();
        setAuthState({ status: "unauthenticated", user: null, error: null });
      },
    }),
    [authState.user],
  );

  if (authState.status === "checking") {
    return (
      <section className="auth-card" aria-live="polite">
        <p className="eyebrow">Finance OS</p>
        <h1>Personal Budget</h1>
        <p>Checking your session…</p>
      </section>
    );
  }

  if (authState.status === "unauthenticated") {
    return <AuthScreen error={authState.error} onLogin={value.login} onRegister={value.register} />;
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function AuthScreen({
  error,
  onLogin,
  onRegister,
}: {
  error: string | null;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string, displayName: string) => Promise<void>;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(error);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setStatusMessage(null);
    try {
      if (mode === "login") {
        await onLogin(email, password);
      } else {
        await onRegister(email, password, displayName);
      }
    } catch {
      setStatusMessage(mode === "login" ? "Unable to sign in" : "Unable to create account");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <p className="eyebrow">Finance OS</p>
        <h1>{mode === "login" ? "Sign in" : "Create account"}</h1>
        <p>Use your budget account before loading workspaces.</p>
        <form onSubmit={handleSubmit}>
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          {mode === "register" ? (
            <label>
              Display name
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required />
            </label>
          ) : null}
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          <button type="submit" disabled={isSubmitting}>
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button type="button" className="link-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "Create a new account" : "Already have an account? Sign in"}
        </button>
        {statusMessage ? <p role="alert">{statusMessage}</p> : null}
      </section>
    </main>
  );
}
