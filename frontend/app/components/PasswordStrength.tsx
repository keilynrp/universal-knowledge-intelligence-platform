"use client";

import { useLanguage } from "../contexts/LanguageContext";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Criteria {
  label: string;
  met: boolean;
}

interface StrengthResult {
  score: number;       // 0–3
  level: "weak" | "medium" | "strong";
  label: string;
  criteria: Criteria[];
}

// ── Strength calculator ───────────────────────────────────────────────────────

export function getPasswordStrength(password: string): StrengthResult {
  const criteria: Criteria[] = [
    { label: "At least 8 characters",         met: password.length >= 8 },
    { label: "At least 12 characters",         met: password.length >= 12 },
    { label: "Uppercase letter (A–Z)",         met: /[A-Z]/.test(password) },
    { label: "Lowercase letter (a–z)",         met: /[a-z]/.test(password) },
    { label: "Number (0–9)",                   met: /[0-9]/.test(password) },
    { label: "Special character (!@#$…)",      met: /[^A-Za-z0-9]/.test(password) },
  ];

  const passesMinimum = criteria[0].met;
  const bonus = criteria.slice(1).filter(c => c.met).length; // 0–5

  let score: 0 | 1 | 2 | 3;
  if (!passesMinimum)   score = 0;
  else if (bonus <= 1)  score = 1;
  else if (bonus <= 3)  score = 2;
  else                  score = 3;

  const meta: Record<number, { level: StrengthResult["level"]; label: string }> = {
    0: { level: "weak",   label: "Too short" },
    1: { level: "weak",   label: "Weak" },
    2: { level: "medium", label: "Medium" },
    3: { level: "strong", label: "Strong" },
  };

  return { score, ...meta[score], criteria };
}

// ── Colour config ─────────────────────────────────────────────────────────────

const LEVEL_COLOR = {
  weak:   { bar: "bg-red-500",    text: "text-red-600 dark:text-red-400" },
  medium: { bar: "bg-yellow-400", text: "text-yellow-600 dark:text-yellow-400" },
  strong: { bar: "bg-green-500",  text: "text-green-600 dark:text-green-400" },
};

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  password: string;
  /** Show criteria checklist. Default: true */
  showCriteria?: boolean;
}

export default function PasswordStrength({ password, showCriteria = true }: Props) {
  const { t } = useLanguage();
  if (!password) return null;

  const { score, level, label, criteria } = getPasswordStrength(password);
  const { bar, text } = LEVEL_COLOR[level];
  const localizedCriteria = criteria.map((criterion) => ({
    ...criterion,
    label: t(
      criterion.label === "At least 8 characters" ? "settings.account.password_rule_min_8"
        : criterion.label === "At least 12 characters" ? "settings.account.password_rule_min_12"
          : criterion.label === "Uppercase letter (A–Z)" ? "settings.account.password_rule_upper"
            : criterion.label === "Lowercase letter (a–z)" ? "settings.account.password_rule_lower"
              : criterion.label === "Number (0–9)" ? "settings.account.password_rule_number"
                : "settings.account.password_rule_special",
    ),
  }));
  const localizedLabel =
    label === "Too short" ? t("settings.account.password_label_short")
      : label === "Weak" ? t("settings.account.password_label_weak")
        : label === "Medium" ? t("settings.account.password_label_medium")
          : t("settings.account.password_label_strong");

  return (
    <div className="mt-2 space-y-2">
      {/* Bar + label */}
      <div className="flex items-center gap-3">
        <div className="flex flex-1 gap-1">
          {[1, 2, 3].map(seg => (
            <div
              key={seg}
              className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
                seg <= score ? bar : "bg-gray-200 dark:bg-gray-700"
              }`}
            />
          ))}
        </div>
        <span className={`shrink-0 text-xs font-semibold ${text}`}>{localizedLabel}</span>
      </div>

      {/* Criteria checklist */}
      {showCriteria && (
        <ul className="grid grid-cols-1 gap-0.5 sm:grid-cols-2">
          {localizedCriteria.map(c => (
            <li key={c.label} className="flex items-center gap-1.5 text-[11px]">
              {c.met ? (
                <svg className="h-3.5 w-3.5 shrink-0 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="h-3.5 w-3.5 shrink-0 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="9" strokeWidth={2} />
                </svg>
              )}
              <span className={c.met ? "text-gray-600 dark:text-gray-300" : "text-gray-400 dark:text-gray-500"}>
                {c.label}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
