"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

type TriggerType = "entity.created" | "entity.enriched" | "entity.flagged" | "manual";
type ConditionType = "field_equals" | "field_contains" | "field_empty" | "enrichment_status_is";
type ActionType = "send_webhook" | "tag_entity" | "send_alert" | "log_only";

interface Condition {
  type: ConditionType;
  field: string;
  value: string;
}

interface Action {
  type: ActionType;
  config: Record<string, unknown>;
}

interface Workflow {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  trigger_type: TriggerType;
  conditions: Condition[];
  actions: Action[];
  run_count: number;
  last_run_at: string | null;
  last_run_status: string | null;
  created_at: string | null;
}

interface WorkflowRun {
  id: number;
  workflow_id: number;
  status: string;
  trigger_data: Record<string, unknown>;
  steps_log: Array<{ action: string; result: Record<string, unknown> }>;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

// ── Constants ──────────────────────────────────────────────────────────────

const TRIGGER_LABELS: Record<TriggerType, string> = {
  "entity.created": "Entity Created",
  "entity.enriched": "Entity Enriched",
  "entity.flagged": "Entity Flagged",
  manual: "Manual",
};

const TRIGGER_COLORS: Record<TriggerType, string> = {
  "entity.created": "bg-emerald-100 text-emerald-800",
  "entity.enriched": "bg-blue-100 text-blue-800",
  "entity.flagged": "bg-rose-100 text-rose-800",
  manual: "bg-violet-100 text-violet-800",
};

const STATUS_COLORS: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-700",
  error: "bg-rose-100 text-rose-700",
  skipped: "bg-amber-100 text-amber-700",
  running: "bg-blue-100 text-blue-700",
};

const CONDITION_TYPES: Array<{ value: ConditionType; label: string }> = [
  { value: "field_equals", label: "Field equals" },
  { value: "field_contains", label: "Field contains" },
  { value: "field_empty", label: "Field is empty" },
  { value: "enrichment_status_is", label: "Enrichment status is" },
];

const ACTION_TYPES: Array<{ value: ActionType; label: string; description: string }> = [
  { value: "send_webhook", label: "Send Webhook", description: "POST JSON to a URL" },
  { value: "tag_entity", label: "Tag Entity", description: "Append a concept tag" },
  { value: "send_alert", label: "Send Alert", description: "Fire a notification channel" },
  { value: "log_only", label: "Log Only", description: "Record run (no external calls)" },
];

// ── Empty state helpers ────────────────────────────────────────────────────

const emptyCondition = (): Condition => ({ type: "field_equals", field: "", value: "" });
const emptyAction = (): Action => ({ type: "log_only", config: {} });

// ── Sub-components ─────────────────────────────────────────────────────────

function Badge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function ConditionEditor({
  condition,
  index,
  onChange,
  onRemove,
}: {
  condition: Condition;
  index: number;
  onChange: (i: number, c: Condition) => void;
  onRemove: (i: number) => void;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex-1 grid grid-cols-3 gap-2">
        <select
          value={condition.type}
          onChange={(e) => onChange(index, { ...condition, type: e.target.value as ConditionType })}
          className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
        >
          {CONDITION_TYPES.map((ct) => (
            <option key={ct.value} value={ct.value}>{ct.label}</option>
          ))}
        </select>
        <input
          placeholder="field name"
          value={condition.field}
          onChange={(e) => onChange(index, { ...condition, field: e.target.value })}
          className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          disabled={condition.type === "enrichment_status_is"}
        />
        <input
          placeholder="value"
          value={condition.value}
          onChange={(e) => onChange(index, { ...condition, value: e.target.value })}
          className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          disabled={condition.type === "field_empty"}
        />
      </div>
      <button
        onClick={() => onRemove(index)}
        className="mt-1 text-slate-400 hover:text-rose-500"
        title="Remove condition"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

function ActionEditor({
  action,
  index,
  onChange,
  onRemove,
}: {
  action: Action;
  index: number;
  onChange: (i: number, a: Action) => void;
  onRemove: (i: number) => void;
}) {
  const updateConfig = (key: string, value: unknown) =>
    onChange(index, { ...action, config: { ...action.config, [key]: value } });

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <select
          value={action.type}
          onChange={(e) => onChange(index, { type: e.target.value as ActionType, config: {} })}
          className="flex-1 rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
        >
          {ACTION_TYPES.map((at) => (
            <option key={at.value} value={at.value}>{at.label} — {at.description}</option>
          ))}
        </select>
        <button onClick={() => onRemove(index)} className="text-slate-400 hover:text-rose-500">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {action.type === "send_webhook" && (
        <input
          placeholder="Webhook URL (https://...)"
          value={(action.config.url as string) || ""}
          onChange={(e) => updateConfig("url", e.target.value)}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        />
      )}
      {action.type === "tag_entity" && (
        <input
          placeholder="Tag to append (e.g. auto-reviewed)"
          value={(action.config.tag as string) || ""}
          onChange={(e) => updateConfig("tag", e.target.value)}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        />
      )}
      {action.type === "send_alert" && (
        <div className="grid grid-cols-2 gap-2">
          <input
            placeholder="Alert Channel ID"
            type="number"
            value={(action.config.channel_id as number) || ""}
            onChange={(e) => updateConfig("channel_id", parseInt(e.target.value))}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          />
          <input
            placeholder="Message (optional)"
            value={(action.config.message as string) || ""}
            onChange={(e) => updateConfig("message", e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
      )}
    </div>
  );
}

// ── Workflow form (create / edit) ─────────────────────────────────────────

function WorkflowForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<Workflow>;
  onSave: (data: Partial<Workflow>) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [trigger, setTrigger] = useState<TriggerType>(initial?.trigger_type ?? "manual");
  const [conditions, setConditions] = useState<Condition[]>(initial?.conditions ?? []);
  const [actions, setActions] = useState<Action[]>(initial?.actions ?? [emptyAction()]);

  const updateCondition = (i: number, c: Condition) =>
    setConditions((cs) => cs.map((x, j) => (j === i ? c : x)));
  const removeCondition = (i: number) => setConditions((cs) => cs.filter((_, j) => j !== i));
  const updateAction = (i: number, a: Action) =>
    setActions((as) => as.map((x, j) => (j === i ? a : x)));
  const removeAction = (i: number) => setActions((as) => as.filter((_, j) => j !== i));

  const handleSubmit = () => {
    if (!name.trim()) return;
    onSave({ name, description, is_active: isActive, trigger_type: trigger, conditions, actions });
  };

  return (
    <div className="space-y-6">
      {/* Basic info */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Workflow"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Trigger</label>
          <select
            value={trigger}
            onChange={(e) => setTrigger(e.target.value as TriggerType)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            {Object.entries(TRIGGER_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex items-end gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 rounded accent-violet-600"
            />
            Active
          </label>
        </div>
      </div>

      {/* Conditions */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-slate-700">
            Conditions <span className="text-slate-400 font-normal">(all must match — leave empty to always run)</span>
          </h3>
          <button
            onClick={() => setConditions((cs) => [...cs, emptyCondition()])}
            className="text-xs text-violet-600 hover:text-violet-800 font-medium"
          >
            + Add condition
          </button>
        </div>
        <div className="space-y-2">
          {conditions.length === 0 && (
            <p className="text-sm text-slate-400 italic py-2">No conditions — workflow always runs.</p>
          )}
          {conditions.map((c, i) => (
            <ConditionEditor key={i} condition={c} index={i} onChange={updateCondition} onRemove={removeCondition} />
          ))}
        </div>
      </div>

      {/* Actions */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-slate-700">Actions</h3>
          <button
            onClick={() => setActions((as) => [...as, emptyAction()])}
            className="text-xs text-violet-600 hover:text-violet-800 font-medium"
          >
            + Add action
          </button>
        </div>
        <div className="space-y-2">
          {actions.map((a, i) => (
            <ActionEditor key={i} action={a} index={i} onChange={updateAction} onRemove={removeAction} />
          ))}
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-2 border-t border-slate-200">
        <button onClick={onCancel} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={!name.trim()}
          className="px-5 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50"
        >
          Save Workflow
        </button>
      </div>
    </div>
  );
}

// ── Run history panel ─────────────────────────────────────────────────────

function RunHistoryPanel({ workflowId, onClose }: { workflowId: number; onClose: () => void }) {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/workflows/${workflowId}/runs`)
      .then((r) => r.json())
      .then((d) => setRuns(d.items || []))
      .finally(() => setLoading(false));
  }, [workflowId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Execution History</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="overflow-y-auto flex-1 p-6">
          {loading ? (
            <p className="text-sm text-slate-400">Loading runs…</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-slate-400">No runs yet.</p>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <div key={run.id} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[run.status] || "bg-slate-100 text-slate-700"}`}>
                        {run.status}
                      </span>
                      <span className="text-xs text-slate-500">
                        {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
                      </span>
                    </div>
                    {run.completed_at && run.started_at && (
                      <span className="text-xs text-slate-400">
                        {Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()))}ms
                      </span>
                    )}
                  </div>
                  {run.steps_log.length > 0 && (
                    <div className="space-y-1">
                      {run.steps_log.map((step, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs text-slate-600">
                          <span className={step.result.ok ? "text-emerald-500" : "text-rose-500"}>
                            {step.result.ok ? "✓" : "✗"}
                          </span>
                          <span className="font-mono">{step.action}</span>
                          {!step.result.ok && (
                            <span className="text-rose-500">{String(step.result.error || "")}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {run.error && <p className="text-xs text-rose-600 mt-1">{run.error}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Manual run dialog ──────────────────────────────────────────────────────

function ManualRunDialog({
  workflowId,
  onClose,
  onComplete,
}: {
  workflowId: number;
  onClose: () => void;
  onComplete: () => void;
}) {
  const [entityId, setEntityId] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<WorkflowRun | null>(null);
  const [error, setError] = useState("");

  const handleRun = async () => {
    if (!entityId) return;
    setRunning(true);
    setError("");
    try {
      const res = await apiFetch(`/workflows/${workflowId}/run`, {
        method: "POST",
        body: JSON.stringify({ entity_id: parseInt(entityId) }),
      });
      const run = await res.json();
      setResult(run);
      onComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Manual Run</h2>
        {!result ? (
          <>
            <label className="block text-sm font-medium text-slate-700 mb-1">Entity ID</label>
            <input
              type="number"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="Enter entity ID"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mb-4"
            />
            {error && <p className="text-sm text-rose-600 mb-3">{error}</p>}
            <div className="flex justify-end gap-3">
              <button onClick={onClose} className="text-sm text-slate-600 hover:text-slate-900">Cancel</button>
              <button
                onClick={handleRun}
                disabled={!entityId || running}
                className="px-5 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50"
              >
                {running ? "Running…" : "Run Now"}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium mb-3 ${STATUS_COLORS[result.status] || "bg-slate-100"}`}>
              {result.status}
            </div>
            <div className="space-y-1 mb-4">
              {result.steps_log.map((step, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className={step.result.ok ? "text-emerald-500" : "text-rose-500"}>
                    {step.result.ok ? "✓" : "✗"}
                  </span>
                  <span className="font-mono text-xs">{step.action}</span>
                </div>
              ))}
            </div>
            <button onClick={onClose} className="w-full py-2 rounded-lg bg-slate-100 text-slate-700 text-sm hover:bg-slate-200">
              Close
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Workflow | null>(null);
  const [historyFor, setHistoryFor] = useState<number | null>(null);
  const [manualRunFor, setManualRunFor] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    apiFetch("/workflows")
      .then((r) => r.json())
      .then((d) => setWorkflows(d.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (data: Partial<Workflow>) => {
    try {
      await apiFetch("/workflows", { method: "POST", body: JSON.stringify(data) });
      setShowCreate(false);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
    }
  };

  const handleUpdate = async (data: Partial<Workflow>) => {
    if (!editing) return;
    try {
      await apiFetch(`/workflows/${editing.id}`, { method: "PUT", body: JSON.stringify(data) });
      setEditing(null);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this workflow?")) return;
    try {
      await apiFetch(`/workflows/${id}`, { method: "DELETE" });
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const handleToggle = async (wf: Workflow) => {
    try {
      await apiFetch(`/workflows/${wf.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !wf.is_active }),
      });
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-violet-50 p-6">
      <div className="mx-auto max-w-5xl space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Workflow Automation</h1>
            <p className="text-sm text-slate-500 mt-1">
              Build no-code trigger → condition → action chains to automate data operations.
            </p>
          </div>
          <button
            onClick={() => { setShowCreate(true); setEditing(null); }}
            className="flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-violet-700 shadow-sm"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Workflow
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {/* Create / Edit form */}
        {(showCreate || editing) && (
          <div className="rounded-xl bg-white border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-5">
              {editing ? "Edit Workflow" : "New Workflow"}
            </h2>
            <WorkflowForm
              initial={editing ?? undefined}
              onSave={editing ? handleUpdate : handleCreate}
              onCancel={() => { setShowCreate(false); setEditing(null); }}
            />
          </div>
        )}

        {/* Workflow list */}
        {loading ? (
          <div className="text-center py-16 text-slate-400">Loading workflows…</div>
        ) : workflows.length === 0 && !showCreate ? (
          <div className="rounded-xl bg-white border border-slate-200 p-16 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-violet-100">
              <svg className="h-8 w-8 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-slate-800">No workflows yet</h3>
            <p className="mt-1 text-sm text-slate-500">Create your first workflow to automate data operations.</p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-700"
            >
              Create Workflow
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {workflows.map((wf) => (
              <div
                key={wf.id}
                className={`rounded-xl bg-white border shadow-sm p-5 transition-opacity ${wf.is_active ? "border-slate-200" : "border-slate-100 opacity-60"}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-slate-900 truncate">{wf.name}</h3>
                      <Badge
                        label={TRIGGER_LABELS[wf.trigger_type] || wf.trigger_type}
                        className={TRIGGER_COLORS[wf.trigger_type] || "bg-slate-100 text-slate-700"}
                      />
                      {!wf.is_active && <Badge label="Inactive" className="bg-slate-100 text-slate-500" />}
                      {wf.last_run_status && (
                        <Badge
                          label={wf.last_run_status}
                          className={STATUS_COLORS[wf.last_run_status] || "bg-slate-100 text-slate-700"}
                        />
                      )}
                    </div>
                    {wf.description && (
                      <p className="text-sm text-slate-500 mt-1 truncate">{wf.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                      <span>{wf.conditions.length} condition{wf.conditions.length !== 1 ? "s" : ""}</span>
                      <span>{wf.actions.length} action{wf.actions.length !== 1 ? "s" : ""}</span>
                      <span>{wf.run_count} run{wf.run_count !== 1 ? "s" : ""}</span>
                      {wf.last_run_at && (
                        <span>Last run {new Date(wf.last_run_at).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {/* Toggle active */}
                    <button
                      onClick={() => handleToggle(wf)}
                      title={wf.is_active ? "Deactivate" : "Activate"}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${wf.is_active ? "bg-violet-600" : "bg-slate-300"}`}
                    >
                      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${wf.is_active ? "translate-x-4" : "translate-x-1"}`} />
                    </button>

                    {/* Manual run */}
                    <button
                      onClick={() => setManualRunFor(wf.id)}
                      title="Manual run"
                      className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:text-violet-600 hover:border-violet-300"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                      </svg>
                    </button>

                    {/* History */}
                    <button
                      onClick={() => setHistoryFor(wf.id)}
                      title="Run history"
                      className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:text-violet-600 hover:border-violet-300"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </button>

                    {/* Edit */}
                    <button
                      onClick={() => { setEditing(wf); setShowCreate(false); }}
                      title="Edit"
                      className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:text-violet-600 hover:border-violet-300"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                      </svg>
                    </button>

                    {/* Delete */}
                    <button
                      onClick={() => handleDelete(wf.id)}
                      title="Delete"
                      className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:text-rose-600 hover:border-rose-200"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      {historyFor !== null && (
        <RunHistoryPanel workflowId={historyFor} onClose={() => setHistoryFor(null)} />
      )}
      {manualRunFor !== null && (
        <ManualRunDialog
          workflowId={manualRunFor}
          onClose={() => setManualRunFor(null)}
          onComplete={() => { setManualRunFor(null); load(); }}
        />
      )}
    </div>
  );
}
