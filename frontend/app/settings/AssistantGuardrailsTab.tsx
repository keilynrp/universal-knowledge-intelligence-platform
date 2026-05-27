"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ToastVariant } from "../components/ui";

type AssistantCapability = {
  id: string;
  label: string;
  description: string;
  kind: string;
  risk: "low" | "medium" | "high";
  enabled: boolean;
  allowed_roles: string[];
  requires_confirmation: boolean;
  rollback: "none" | "manual" | "snapshot";
  configured: boolean;
};

const ROLES = ["super_admin", "admin", "editor", "viewer"];

function riskStyle(risk: AssistantCapability["risk"]) {
  if (risk === "high") return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
  if (risk === "medium") return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
  return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300";
}

export default function AssistantGuardrailsTab({
  toast,
}: {
  toast: (msg: string, v?: ToastVariant) => void;
}) {
  const [items, setItems] = useState<AssistantCapability[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const response = await apiFetch("/assistant/actions");
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail ?? "No se pudieron cargar guardrails.");
      setItems(payload.items ?? []);
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudieron cargar guardrails.", "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function save(item: AssistantCapability, patch: Partial<AssistantCapability>) {
    setSavingId(item.id);
    try {
      const response = await apiFetch(`/assistant/actions/${item.id}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail ?? "No se pudo guardar el guardrail.");
      setItems((current) => current.map((candidate) => candidate.id === item.id ? payload : candidate));
      toast("Guardrail actualizado.", "success");
    } catch (error) {
      toast(error instanceof Error ? error.message : "No se pudo guardar el guardrail.", "error");
    } finally {
      setSavingId(null);
    }
  }

  function toggleRole(item: AssistantCapability, role: string) {
    const hasRole = item.allowed_roles.includes(role);
    const nextRoles = hasRole
      ? item.allowed_roles.filter((candidate) => candidate !== role)
      : [...item.allowed_roles, role];
    if (nextRoles.length === 0) {
      toast("Cada accion necesita al menos un rol permitido.", "warning");
      return;
    }
    void save(item, { allowed_roles: nextRoles });
  }

  if (loading) {
    return <div className="rounded-2xl border border-gray-200 bg-white p-6 text-sm text-gray-500 dark:border-gray-800 dark:bg-gray-900">Cargando guardrails del Assistant...</div>;
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-violet-200 bg-violet-50/80 p-4 dark:border-violet-900/30 dark:bg-violet-900/10">
        <p className="text-sm font-semibold text-violet-950 dark:text-violet-100">Capacidades operativas del UKIP Assistant</p>
        <p className="mt-1 text-xs leading-5 text-violet-900/80 dark:text-violet-200/80">
          Este registro controla que acciones puede ejecutar el Assistant, que roles estan autorizados, si requieren confirmacion y como se clasifica su rollback.
        </p>
      </div>

      <div className="grid gap-4">
        {items.map((item) => (
          <section key={item.id} className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold text-gray-900 dark:text-white">{item.label}</h3>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${riskStyle(item.risk)}`}>{item.risk}</span>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600 dark:bg-gray-800 dark:text-gray-300">{item.kind}</span>
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">rollback: {item.rollback}</span>
                </div>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{item.description}</p>
                <code className="mt-3 inline-block rounded bg-gray-100 px-2 py-1 text-xs text-gray-600 dark:bg-gray-950 dark:text-gray-300">{item.id}</code>
              </div>
              <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={item.enabled}
                  disabled={savingId === item.id}
                  onChange={(event) => void save(item, { enabled: event.target.checked })}
                  className="h-4 w-4 rounded border-gray-300 text-violet-600 focus:ring-violet-500"
                />
                Habilitada
              </label>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-[1fr,auto]">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Roles permitidos</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {ROLES.map((role) => (
                    <button
                      key={role}
                      type="button"
                      disabled={savingId === item.id}
                      onClick={() => toggleRole(item, role)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                        item.allowed_roles.includes(role)
                          ? "border-violet-300 bg-violet-100 text-violet-700 dark:border-violet-700 dark:bg-violet-900/30 dark:text-violet-200"
                          : "border-gray-300 bg-white text-gray-500 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-400"
                      }`}
                    >
                      {role}
                    </button>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={item.requires_confirmation}
                  disabled={savingId === item.id}
                  onChange={(event) => void save(item, { requires_confirmation: event.target.checked })}
                  className="h-4 w-4 rounded border-gray-300 text-violet-600 focus:ring-violet-500"
                />
                Requiere confirmacion
              </label>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
