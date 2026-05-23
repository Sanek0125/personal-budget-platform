export type NavigationItem = {
  label: string;
  path: string;
};

export const navigationItems: NavigationItem[] = [
  { label: "Dashboard", path: "/" },
  { label: "Transactions", path: "/transactions" },
  { label: "Accounts", path: "/accounts" },
  { label: "Categories", path: "/categories" },
  { label: "Imports", path: "/imports" },
  { label: "Budgets", path: "/budgets" },
  { label: "Debts", path: "/debts" },
  { label: "Rewards", path: "/rewards" },
  { label: "Settings", path: "/settings" },
];
