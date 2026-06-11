import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: string | number): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const CATEGORY_COLORS: Record<string, string> = {
  "Food & Dining": "#f97316",
  "Shopping": "#8b5cf6",
  "Fuel": "#eab308",
  "Travel": "#06b6d4",
  "Bills & Utilities": "#64748b",
  "Entertainment": "#ec4899",
  "Healthcare": "#22c55e",
  "Education": "#3b82f6",
  "Investments": "#10b981",
  "EMI / Loans": "#ef4444",
  "ATM Withdrawal": "#6b7280",
  "Subscriptions": "#a855f7",
  "Insurance": "#14b8a6",
  "Others": "#94a3b8",
};
