import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "../../api/client";
import type {
  Category,
  CategoryCreatePayload,
  CategoryRule,
  CategoryRuleApplyResult,
  CategoryRuleCreatePayload,
  CategoryRuleMatchField,
  CategoryRuleOperator,
  CategoryType,
  Workspace,
} from "../../types";

export function CategoriesPage({ activeWorkspace }: { activeWorkspace?: Workspace }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [categoryType, setCategoryType] = useState<CategoryType>("expense");
  const [color, setColor] = useState("");
  const [icon, setIcon] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [ruleName, setRuleName] = useState("");
  const [ruleCategoryId, setRuleCategoryId] = useState("");
  const [ruleMatchField, setRuleMatchField] = useState<CategoryRuleMatchField>("description");
  const [ruleOperator, setRuleOperator] = useState<CategoryRuleOperator>("contains");
  const [rulePattern, setRulePattern] = useState("");
  const [ruleAmountMin, setRuleAmountMin] = useState("");
  const [ruleAmountMax, setRuleAmountMax] = useState("");
  const [rulePriority, setRulePriority] = useState("100");
  const [ruleIsActive, setRuleIsActive] = useState(true);
  const [ruleStatusMessage, setRuleStatusMessage] = useState<string | null>(null);
  const [applyStatusMessage, setApplyStatusMessage] = useState<string | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ["categories", activeWorkspace?.id],
    queryFn: () => apiGet<Category[]>(`/workspaces/${activeWorkspace?.id}/categories`),
    enabled: Boolean(activeWorkspace),
  });
  const categoryRulesQuery = useQuery({
    queryKey: ["category-rules", activeWorkspace?.id],
    queryFn: () => apiGet<CategoryRule[]>(`/workspaces/${activeWorkspace?.id}/category-rules`),
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

  async function handleCreateRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspace) {
      setRuleStatusMessage("Select a workspace before creating category rules");
      return;
    }

    const payload: CategoryRuleCreatePayload = {
      name: ruleName.trim(),
      category_id: ruleCategoryId,
      operator: ruleOperator,
      match_field: ruleMatchField,
      ...(rulePattern.trim() ? { pattern: rulePattern.trim() } : {}),
      ...(ruleAmountMin.trim() ? { amount_min: ruleAmountMin.trim() } : {}),
      ...(ruleAmountMax.trim() ? { amount_max: ruleAmountMax.trim() } : {}),
      priority: Number.parseInt(rulePriority, 10) || 100,
      is_active: ruleIsActive,
    };

    try {
      const rule = await apiPost<CategoryRule, CategoryRuleCreatePayload>(
        `/workspaces/${activeWorkspace.id}/category-rules`,
        payload,
      );
      setRuleStatusMessage(`Created category rule ${rule.name}`);
      setRuleName("");
      setRuleCategoryId("");
      setRuleMatchField("description");
      setRuleOperator("contains");
      setRulePattern("");
      setRuleAmountMin("");
      setRuleAmountMax("");
      setRulePriority("100");
      setRuleIsActive(true);
      await queryClient.invalidateQueries({ queryKey: ["category-rules", activeWorkspace.id] });
    } catch {
      setRuleStatusMessage("Unable to create category rule");
    }
  }

  async function handleApplyRules() {
    if (!activeWorkspace) {
      setApplyStatusMessage("Select a workspace before applying rules");
      return;
    }

    try {
      const result = await apiPost<CategoryRuleApplyResult, Record<string, never>>(
        `/workspaces/${activeWorkspace.id}/category-rules/apply`,
        {},
      );
      setApplyStatusMessage(`Categorized ${result.categorized_count} of ${result.evaluated_count} transactions`);
      await queryClient.invalidateQueries({ queryKey: ["transactions", activeWorkspace.id] });
    } catch {
      setApplyStatusMessage("Unable to apply category rules");
    }
  }

  function categoryName(categoryId: string) {
    return categoriesQuery.data?.find((category) => category.id === categoryId)?.name ?? "Unknown category";
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

        <form className="settings-panel" onSubmit={handleCreateRule}>
          <h3>Create category rule</h3>
          <label>
            Rule name
            <input value={ruleName} onChange={(event) => setRuleName(event.target.value)} minLength={1} required />
          </label>
          <label>
            Rule category
            <select
              value={ruleCategoryId}
              onChange={(event) => setRuleCategoryId(event.target.value)}
              disabled={!categoriesQuery.data?.length}
              required
            >
              <option value="">Choose category</option>
              {categoriesQuery.data?.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Match field
            <select value={ruleMatchField} onChange={(event) => setRuleMatchField(event.target.value as CategoryRuleMatchField)}>
              <option value="description">description</option>
              <option value="merchant_name">merchant_name</option>
              <option value="merchant_raw">merchant_raw</option>
            </select>
          </label>
          <label>
            Operator
            <select value={ruleOperator} onChange={(event) => setRuleOperator(event.target.value as CategoryRuleOperator)}>
              <option value="contains">contains</option>
              <option value="equals">equals</option>
              <option value="starts_with">starts_with</option>
              <option value="regex">regex</option>
              <option value="amount_between">amount_between</option>
            </select>
          </label>
          <label>
            Pattern
            <input value={rulePattern} onChange={(event) => setRulePattern(event.target.value)} placeholder="perekrestok" />
          </label>
          <label>
            Amount min
            <input inputMode="decimal" value={ruleAmountMin} onChange={(event) => setRuleAmountMin(event.target.value)} />
          </label>
          <label>
            Amount max
            <input inputMode="decimal" value={ruleAmountMax} onChange={(event) => setRuleAmountMax(event.target.value)} />
          </label>
          <label>
            Priority
            <input inputMode="numeric" value={rulePriority} onChange={(event) => setRulePriority(event.target.value)} />
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={ruleIsActive} onChange={(event) => setRuleIsActive(event.target.checked)} />
            Active rule
          </label>
          <button type="submit" disabled={!activeWorkspace || !categoriesQuery.data?.length}>Create rule</button>
          {ruleStatusMessage ? <p role="status">{ruleStatusMessage}</p> : null}
        </form>

        <div className="settings-panel">
          <h3>Category rules</h3>
          {categoryRulesQuery.isLoading ? <p>Loading category rules…</p> : null}
          {categoryRulesQuery.isError ? <p role="alert">Unable to load category rules</p> : null}
          {categoryRulesQuery.data?.length === 0 ? <p>No category rules yet.</p> : null}
          {categoryRulesQuery.data?.length ? (
            <ul className="entity-list">
              {categoryRulesQuery.data.map((rule) => (
                <li key={rule.id}>
                  <strong>{rule.name}</strong>
                  <span>{categoryName(rule.category_id)}</span>
                  <span>
                    {rule.match_field} · {rule.operator} · {rule.pattern ?? `${rule.amount_min ?? ""}–${rule.amount_max ?? ""}`}
                  </span>
                  <span>Priority: {rule.priority} · {rule.is_active ? "active" : "inactive"}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <button type="button" onClick={handleApplyRules} disabled={!activeWorkspace || !categoryRulesQuery.data?.length}>
            Apply active rules
          </button>
          {applyStatusMessage ? <p role="status">{applyStatusMessage}</p> : null}
        </div>
      </div>
    </section>
  );
}
