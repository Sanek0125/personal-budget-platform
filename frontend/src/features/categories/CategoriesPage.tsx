import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type { Category, CategoryCreatePayload, CategoryType, Workspace } from "../../types";

export function CategoriesPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [categoryType, setCategoryType] = useState<CategoryType>("expense");
  const [color, setColor] = useState("");
  const [icon, setIcon] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ["categories", activeWorkspace?.id],
    queryFn: () => apiGet<Category[]>(`/workspaces/${activeWorkspace?.id}/categories`),
    enabled: Boolean(activeWorkspace),
  });

  async function handleCreateCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setStatusMessage("Select a workspace before creating categories");
      return;
    }

    setStatusMessage(null);
    const payload: CategoryCreatePayload = {
      name: name.trim(),
      type: categoryType,
      ...(color.trim() ? { color: color.trim() } : {}),
      ...(icon.trim() ? { icon: icon.trim() } : {}),
      sort_order: Number.parseInt(sortOrder, 10) || 0,
    };

    try {
      const category = await apiPost<Category, CategoryCreatePayload>(
        `/workspaces/${activeWorkspace.id}/categories`,
        payload,
      );
      setStatusMessage(`Created category ${category.name}`);
      setName("");
      setCategoryType("expense");
      setColor("");
      setIcon("");
      setSortOrder("0");
      await queryClient.invalidateQueries({ queryKey: ["categories", activeWorkspace.id] });
    } catch {
      setStatusMessage("Unable to create category");
    }
  }

  return (
    <section className="page-card categories-page">
      <p className="eyebrow">MVP module</p>
      <h2>Categories</h2>
      <p>Hierarchical categories and auto-categorization rules.</p>

      <div className="settings-grid">
        <form className="settings-panel" onSubmit={handleCreateCategory}>
          <h3>Create category</h3>
          <p>
            Active workspace: <strong>{activeWorkspace?.name ?? "none"}</strong>
          </p>
          <label>
            Category name
            <input value={name} onChange={(event) => setName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Category type
            <select value={categoryType} onChange={(event) => setCategoryType(event.target.value as CategoryType)}>
              <option value="expense">expense</option>
              <option value="income">income</option>
              <option value="transfer">transfer</option>
              <option value="mixed">mixed</option>
            </select>
          </label>
          <label>
            Color
            <input value={color} onChange={(event) => setColor(event.target.value)} placeholder="#22c55e" />
          </label>
          <label>
            Icon
            <input value={icon} onChange={(event) => setIcon(event.target.value)} placeholder="cart" />
          </label>
          <label>
            Sort order
            <input
              inputMode="numeric"
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value)}
            />
          </label>
          <button type="submit" disabled={!activeWorkspace}>Create category</button>
          {statusMessage ? <p role="status">{statusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Category list</h3>
          {!activeWorkspace ? <p>Select a workspace to load categories.</p> : null}
          {categoriesQuery.isLoading ? <p>Loading categories…</p> : null}
          {categoriesQuery.isError ? <p role="alert">Unable to load categories</p> : null}
          {categoriesQuery.data?.length === 0 ? <p>No categories yet.</p> : null}
          {categoriesQuery.data?.length ? (
            <ul className="entity-list">
              {categoriesQuery.data.map((category) => (
                <li key={category.id}>
                  <strong>{category.name}</strong>
                  <span>{[category.type, category.color, category.icon].filter(Boolean).join(" · ")}</span>
                  {category.parent_id ? <span>Parent: {category.parent_id}</span> : null}
                  <span>Sort order: {category.sort_order}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}
