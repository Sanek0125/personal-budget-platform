import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";


import { App } from "./App";

afterEach(() => {
  cleanup();
});

describe("App shell", () => {
  it("renders the dashboard layout with core personal-budget navigation", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /personal budget/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /transactions/i })).toHaveAttribute("href", "/transactions");
    expect(screen.getByRole("link", { name: /accounts/i })).toHaveAttribute("href", "/accounts");
    expect(screen.getByRole("link", { name: /imports/i })).toHaveAttribute("href", "/imports");
    expect(screen.getByRole("link", { name: /budgets/i })).toHaveAttribute("href", "/budgets");
    expect(screen.getByRole("link", { name: /debts/i })).toHaveAttribute("href", "/debts");
    expect(screen.getByRole("link", { name: /rewards/i })).toHaveAttribute("href", "/rewards");
    expect(screen.getByText(/select a workspace/i)).toBeInTheDocument();
  });

  it("routes to feature placeholders from sidebar links", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: /transactions/i }));

    expect(screen.getByRole("heading", { name: /transactions/i })).toBeInTheDocument();
    expect(screen.getByText(/manual entries, splits, transfers, and imported operations/i)).toBeInTheDocument();
  });

  it("renders a not-found page for unknown routes", () => {
    window.history.pushState({}, "", "/missing-page");

    render(<App />);

    expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute("href", "/");
  });
});
