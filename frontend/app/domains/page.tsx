"use client";

import { useState } from "react";
import { useDomain, DomainSchema, DomainAttribute } from "../contexts/DomainContext";
import { useAuth } from "../contexts/AuthContext";
import { apiFetch } from "@/lib/api";

const BUILTIN_IDS = new Set(["default", "science", "healthcare"]);

const TYPE_COLORS: Record<string, string> = {
  string:  "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  integer: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  float:   "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  boolean: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  array:   "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
};

const ICON_OPTIONS = ["Database", "Microscope", "Heart", "Building", "BookOpen", "Globe", "Briefcase", "FlaskConical"];

function DomainIcon({ icon }: { icon?: string | null }) {
  switch (icon) {
    case "Microscope":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" /></svg>;
    case "Heart":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" /></svg>;
    case "Building":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" /></svg>;
    case "BookOpen":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>;
    case "Globe":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" /></svg>;
    case "Briefcase":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0M12 12.75h.008v.008H12v-.008z" /></svg>;
    case "FlaskConical":
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5" /></svg>;
    default: // Database
      return <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg>;
  }
}

type NewAttr = { name: string; label: string; type: string; required: boolean; is_core: boolean };
const emptyAttr = (): NewAttr => ({ name: "", label: "", type: "string", required: false, is_core: false });

const SLUG_RE = /^[a-z][a-z0-9_]*$/;

export default function DomainsPage() {
  const { domains, activeDomainId, setActiveDomainId, refreshDomains } = useDomain();
  const { user } = useAuth();
  const isAdmin = user?.role === "super_admin" || user?.role === "admin";

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  // New domain form state
  const [formId, setFormId] = useState("");
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formEntity, setFormEntity] = useState("");
  const [formIcon, setFormIcon] = useState("Database");
  const [formAttrs, setFormAttrs] = useState<NewAttr[]>([emptyAttr()]);

  const selectedDomain = domains.find(d => d.id === selectedId) ?? null;

  const flash = (type: "ok" | "err", msg: string) => {
    setFeedback({ type, msg });
    setTimeout(() => setFeedback(null), 4000);
  };

  const resetForm = () => {
    setFormId(""); setFormName(""); setFormDesc(""); setFormEntity("");
    setFormIcon("Database"); setFormAttrs([emptyAttr()]);
  };

  const handleCreate = async () => {
    if (!SLUG_RE.test(formId)) { flash("err", "ID must be lowercase letters, numbers or underscores, starting with a letter"); return; }
    if (!formName.trim() || !formDesc.trim() || !formEntity.trim()) { flash("err", "Name, description and primary entity are required"); return; }
    const invalid = formAttrs.find(a => !SLUG_RE.test(a.name) || !a.label.trim());
    if (invalid) { flash("err", `Attribute "${invalid.name || "(empty)"}" has an invalid name or missing label`); return; }

    setSaving(true);
    try {
      const res = await apiFetch("/domains", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: formId, name: formName, description: formDesc, primary_entity: formEntity, icon: formIcon, attributes: formAttrs }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        flash("err", err.detail ?? "Failed to create domain");
      } else {
        await refreshDomains();
        flash("ok", `Domain "${formName}" created successfully`);
        setShowForm(false);
        resetForm();
        setSelectedId(formId);
      }
    } catch {
      flash("err", "Network error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (domainId: string) => {
    if (!confirm(`Delete domain "${domainId}"? This cannot be undone.`)) return;
    setDeleting(domainId);
    try {
      const res = await apiFetch(`/domains/${domainId}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        flash("err", err.detail ?? "Failed to delete domain");
      } else {
        await refreshDomains();
        flash("ok", `Domain "${domainId}" deleted`);
        if (selectedId === domainId) setSelectedId(null);
      }
    } catch {
      flash("err", "Network error");
    } finally {
      setDeleting(null);
    }
  };

  const updateAttr = (i: number, field: keyof NewAttr, value: string | boolean) => {
    setFormAttrs(prev => prev.map((a, idx) => idx === i ? { ...a, [field]: value } : a));
  };

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Domain Registry</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {domains.length} domain{domains.length !== 1 ? "s" : ""} registered · Active: <span className="font-medium text-blue-600 dark:text-blue-400">{activeDomainId}</span>
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => { setShowForm(true); resetForm(); }}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
            New Domain
          </button>
        )}
      </div>

      {/* Feedback banner */}
      {feedback && (
        <div className={`rounded-lg px-4 py-3 text-sm font-medium ${feedback.type === "ok" ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400" : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"}`}>
          {feedback.msg}
        </div>
      )}

      {/* Main layout */}
      <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
        {/* Domain list */}
        <div className="flex flex-col gap-3 overflow-y-auto">
          {domains.map(d => (
            <button
              key={d.id}
              onClick={() => setSelectedId(d.id)}
              className={`w-full text-left rounded-xl border p-4 transition-all ${
                selectedId === d.id
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-900/10 ring-1 ring-blue-500"
                  : "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-700"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`flex-shrink-0 flex h-9 w-9 items-center justify-center rounded-lg ${
                    selectedId === d.id ? "bg-blue-100 text-blue-600 dark:bg-blue-600/20 dark:text-blue-400" : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                  }`}>
                    <DomainIcon icon={d.icon} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm text-gray-900 dark:text-white truncate">{d.name}</span>
                      {activeDomainId === d.id && (
                        <span className="flex-shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">Active</span>
                      )}
                      {BUILTIN_IDS.has(d.id) && (
                        <span className="flex-shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-800 dark:text-gray-400">built-in</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">{d.primary_entity} · {d.attributes.length} attributes</p>
                  </div>
                </div>
              </div>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{d.description}</p>
              <div className="mt-3 flex items-center gap-2">
                {activeDomainId !== d.id && (
                  <button
                    onClick={e => { e.stopPropagation(); setActiveDomainId(d.id); }}
                    className="rounded-md bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
                  >
                    Set Active
                  </button>
                )}
                {isAdmin && !BUILTIN_IDS.has(d.id) && (
                  <button
                    onClick={e => { e.stopPropagation(); handleDelete(d.id); }}
                    disabled={deleting === d.id}
                    className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50"
                  >
                    {deleting === d.id ? "Deleting…" : "Delete"}
                  </button>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Attributes panel */}
        <div className="col-span-2 rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 overflow-hidden flex flex-col">
          {selectedDomain ? (
            <>
              <div className="flex items-center gap-3 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-600/20 dark:text-blue-400">
                  <DomainIcon icon={selectedDomain.icon} />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">{selectedDomain.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Primary entity: <span className="font-medium">{selectedDomain.primary_entity}</span>
                    <span className="mx-2">·</span>
                    {selectedDomain.attributes.length} attributes
                  </p>
                </div>
              </div>
              <div className="overflow-y-auto flex-1">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800/50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Field Name</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Label</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Type</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Required</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Core</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {selectedDomain.attributes.map((attr: DomainAttribute) => (
                      <tr key={attr.name} className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors">
                        <td className="px-6 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">{attr.name}</td>
                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{attr.label}</td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[attr.type] ?? "bg-gray-100 text-gray-600"}`}>
                            {attr.type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {attr.required
                            ? <span className="text-green-500 dark:text-green-400 font-bold">✓</span>
                            : <span className="text-gray-300 dark:text-gray-600">–</span>}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {attr.is_core
                            ? <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">core</span>
                            : <span className="text-gray-300 dark:text-gray-600">–</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-gray-400 dark:text-gray-600">
              <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg>
              <p className="text-sm">Select a domain to view its attributes</p>
            </div>
          )}
        </div>
      </div>

      {/* New Domain slide-over */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-start justify-end">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowForm(false)} />
          <div className="relative z-10 flex h-full w-full max-w-xl flex-col bg-white shadow-2xl dark:bg-gray-950 overflow-y-auto">
            {/* Form header */}
            <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-800">
              <h3 className="font-semibold text-gray-900 dark:text-white">New Domain Schema</h3>
              <button onClick={() => setShowForm(false)} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <div className="flex-1 space-y-5 px-6 py-5">
              {/* Basic info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Domain ID <span className="text-red-500">*</span></label>
                  <input
                    value={formId} onChange={e => setFormId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                    placeholder="e.g. humanities"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="mt-1 text-xs text-gray-400">Lowercase, no spaces</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Name <span className="text-red-500">*</span></label>
                  <input
                    value={formName} onChange={e => setFormName(e.target.value)}
                    placeholder="e.g. Humanities"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Description <span className="text-red-500">*</span></label>
                <input
                  value={formDesc} onChange={e => setFormDesc(e.target.value)}
                  placeholder="Short description of this domain"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Primary Entity <span className="text-red-500">*</span></label>
                  <input
                    value={formEntity} onChange={e => setFormEntity(e.target.value)}
                    placeholder="e.g. Manuscript"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Icon</label>
                  <select
                    value={formIcon} onChange={e => setFormIcon(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {ICON_OPTIONS.map(ico => <option key={ico} value={ico}>{ico}</option>)}
                  </select>
                </div>
              </div>

              {/* Attributes */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-gray-700 dark:text-gray-300">Attributes <span className="text-red-500">*</span></label>
                  <button
                    onClick={() => setFormAttrs(p => [...p, emptyAttr()])}
                    className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                    Add
                  </button>
                </div>
                <div className="space-y-2">
                  {formAttrs.map((attr, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2 items-center">
                      <input
                        value={attr.name} onChange={e => updateAttr(i, "name", e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                        placeholder="field_name"
                        className="col-span-3 rounded-lg border border-gray-300 px-2 py-1.5 text-xs font-mono dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <input
                        value={attr.label} onChange={e => updateAttr(i, "label", e.target.value)}
                        placeholder="Label"
                        className="col-span-4 rounded-lg border border-gray-300 px-2 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <select
                        value={attr.type} onChange={e => updateAttr(i, "type", e.target.value)}
                        className="col-span-2 rounded-lg border border-gray-300 px-2 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        {["string","integer","float","boolean","array"].map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                      <label className="col-span-1 flex items-center justify-center gap-1 text-xs text-gray-500 cursor-pointer" title="Required">
                        <input type="checkbox" checked={attr.required} onChange={e => updateAttr(i, "required", e.target.checked)} className="rounded" />
                        <span>Req</span>
                      </label>
                      <button
                        onClick={() => setFormAttrs(p => p.filter((_, idx) => idx !== i))}
                        disabled={formAttrs.length === 1}
                        className="col-span-2 flex justify-center text-gray-400 hover:text-red-500 disabled:opacity-30 transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Form footer */}
            <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-800">
              <button onClick={() => setShowForm(false)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={saving}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "Creating…" : "Create Domain"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
