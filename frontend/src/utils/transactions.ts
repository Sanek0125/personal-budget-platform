import type { ManualTransactionType } from "../types";

export function normalizeManualAmount(type: ManualTransactionType, amount: string): string {
  const trimmedAmount = amount.trim();
  if (type === "expense") {
    return trimmedAmount.startsWith("-") ? trimmedAmount : `-${trimmedAmount}`;
  }
  if (type === "income") {
    return trimmedAmount.replace(/^-/, "");
  }
  return trimmedAmount;
}

export function toApiDateTime(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    return `${value}:00.000Z`;
  }
  return new Date(value).toISOString();
}
