"use client";

import ExternalAttentionImport from "../components/ExternalAttentionImport";
import { useLanguage } from "../contexts/LanguageContext";

export default function ExternalAttentionPage() {
  const { t } = useLanguage();

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <ExternalAttentionImport />

        {/* Help panel */}
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50 p-5 h-fit">
          <h4 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-3">
            {t("page.external_attention.help_title")}
          </h4>
          <ul className="text-sm text-zinc-600 dark:text-zinc-400 space-y-2">
            <li className="flex gap-2">
              <span className="text-indigo-500 font-bold">1.</span>
              {t("page.external_attention.step_1")}
            </li>
            <li className="flex gap-2">
              <span className="text-indigo-500 font-bold">2.</span>
              {t("page.external_attention.step_2")}
            </li>
            <li className="flex gap-2">
              <span className="text-indigo-500 font-bold">3.</span>
              {t("page.external_attention.step_3")}
            </li>
            <li className="flex gap-2">
              <span className="text-indigo-500 font-bold">4.</span>
              {t("page.external_attention.step_4")}
            </li>
            <li className="flex gap-2">
              <span className="text-indigo-500 font-bold">5.</span>
              {t("page.external_attention.step_5")}
            </li>
          </ul>

          <h4 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mt-5 mb-2">
            {t("page.external_attention.source_types_title")}
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {["policy", "news", "wikipedia", "repository", "blog", "scholarly_web", "social_web"].map(
              (type) => (
                <span
                  key={type}
                  className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 font-medium"
                >
                  {type}
                </span>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
