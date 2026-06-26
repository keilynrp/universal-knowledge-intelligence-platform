"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { useLanguage } from "../../contexts/LanguageContext";
import { useToast } from "../../components/ui";

interface Organization {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  plan: string;
  benchmark_profile_id: string | null;
  benchmark_profile_overrides: {
    profiles?: Record<string, {
      name?: string;
      description?: string;
      region?: string;
      rules?: Record<string, {
        label?: string;
        threshold?: number;
        priority?: string;
        pass_text?: string;
        fail_text?: string;
      }>;
    }>;
  };
  owner_id: number;
  is_active: boolean;
  member_count: number;
  created_at: string;
}

interface BenchmarkRule {
  id: string;
  label: string;
  metric: string;
  threshold: number;
  priority: string;
  pass_text: string;
  fail_text: string;
}

interface BenchmarkProfile {
  id: string;
  name: string;
  description: string;
  region: string;
  rules_count: number;
  rules: BenchmarkRule[];
  is_default: boolean;
}

interface Member {
  user_id: number;
  org_id: number;
  role: string;
  username: string;
  display_name: string;
  joined_at: string;
}

function PlanBadge({ plan }: { plan: string }) {
  const colors: Record<string, string> = {
    free: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    pro: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
    enterprise: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${colors[plan] ?? colors.free}`}>
      {plan}
    </span>
  );
}

export default function OrganizationsPage() {
  const { t } = useLanguage();
  const { toast } = useToast();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", description: "", plan: "free" });
  const [inviteForm, setInviteForm] = useState({ username: "", role: "member" });
  const [benchmarkProfiles, setBenchmarkProfiles] = useState<BenchmarkProfile[]>([]);
  const [savingBenchmark, setSavingBenchmark] = useState(false);
  const [editingRules, setEditingRules] = useState<Record<string, BenchmarkRule>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tr = useCallback((key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  }, [t]);

  const loadOrgs = useCallback(async () => {
    setLoading(true);
    const r = await apiFetch("/organizations");
    if (r.ok) setOrgs(await r.json());
    setLoading(false);
  }, []);

  const loadMembers = useCallback(async (orgId: number) => {
    const r = await apiFetch(`/organizations/${orgId}/members`);
    if (r.ok) setMembers(await r.json());
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      const r = await apiFetch("/organizations");
      if (!active) {
        return;
      }
      if (r.ok) {
        setOrgs(await r.json());
      }
      setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedOrg) {
      return;
    }

    let active = true;
    (async () => {
      const r = await apiFetch(`/organizations/${selectedOrg.id}/members`);
      if (active && r.ok) {
        setMembers(await r.json());
      }
    })();

    return () => {
      active = false;
    };
  }, [selectedOrg]);

  useEffect(() => {
    if (!selectedOrg) {
      // Reset guard inside a data-fetching effect; suppress set-state-in-effect.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setBenchmarkProfiles([]);
      return;
    }

    let active = true;
    (async () => {
      const r = await apiFetch(`/analytics/benchmarks/profiles?org_id=${selectedOrg.id}`);
      if (active && r.ok) {
        setBenchmarkProfiles(await r.json());
      }
    })();
    return () => {
      active = false;
    };
  }, [selectedOrg]);

  useEffect(() => {
    if (!selectedOrg) {
      // Reset guard inside an effect that derives editing rules below; suppress
      // set-state-in-effect for this intentional clear.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEditingRules({});
      return;
    }

    const selectedProfile = benchmarkProfiles.find((profile) => profile.id === (selectedOrg.benchmark_profile_id ?? ""));
    if (!selectedProfile) {
      setEditingRules({});
      return;
    }

    const ruleOverrides = selectedOrg.benchmark_profile_overrides?.profiles?.[selectedProfile.id]?.rules ?? {};
    const mergedRules = Object.fromEntries(
      selectedProfile.rules.map((rule) => [
        rule.id,
        {
          ...rule,
          ...(ruleOverrides[rule.id] ?? {}),
        },
      ]),
    );
    setEditingRules(mergedRules);
  }, [benchmarkProfiles, selectedOrg]);

  async function createOrg() {
    setSaving(true);
    setError(null);
    const r = await apiFetch("/organizations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (r.ok) {
      setShowCreate(false);
      setForm({ name: "", slug: "", description: "", plan: "free" });
      await loadOrgs();
      toast(tr("page.settings_organizations.toast.created", "Organization created"), "success");
    } else {
      const d = await r.json().catch(() => ({}));
      const message = d.detail ?? tr("page.settings_organizations.error.create_org", "Failed to create organization");
      setError(message);
      toast(message, "error");
    }
    setSaving(false);
  }

  async function inviteMember() {
    if (!selectedOrg) return;
    setSaving(true);
    setError(null);
    const r = await apiFetch(`/organizations/${selectedOrg.id}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inviteForm),
    });
    if (r.ok) {
      setShowInvite(false);
      setInviteForm({ username: "", role: "member" });
      await loadMembers(selectedOrg.id);
      toast(tr("page.settings_organizations.toast.invited", "Member invited"), "success");
    } else {
      const d = await r.json().catch(() => ({}));
      const message = d.detail ?? tr("page.settings_organizations.error.invite_member", "Failed to invite member");
      setError(message);
      toast(message, "error");
    }
    setSaving(false);
  }

  async function removeMember(userId: number) {
    if (!selectedOrg || !confirm(tr("page.settings_organizations.confirm.remove_member", "Remove this member?"))) return;
    const r = await apiFetch(`/organizations/${selectedOrg.id}/members/${userId}`, { method: "DELETE" });
    if (r.ok) {
      await loadMembers(selectedOrg.id);
      toast(tr("page.settings_organizations.toast.member_removed", "Member removed"), "success");
      return;
    }
    toast(tr("page.settings_organizations.error.remove_member", "Failed to remove member"), "error");
  }

  async function switchOrg(orgId: number) {
    const r = await apiFetch(`/organizations/${orgId}/switch`, { method: "POST" });
    if (!r.ok) {
      toast(tr("page.settings_organizations.error.switch_org", "Failed to switch organization"), "error");
      return;
    }
    window.location.reload();
  }

  async function deleteOrg(orgId: number) {
    if (!confirm(tr("page.settings_organizations.confirm.delete_org", "Delete this organization? This cannot be undone."))) return;
    const r = await apiFetch(`/organizations/${orgId}`, { method: "DELETE" });
    if (r.ok) {
      setSelectedOrg(null);
      await loadOrgs();
      toast(tr("page.settings_organizations.toast.deleted", "Organization deleted"), "success");
      return;
    }
    toast(tr("page.settings_organizations.error.delete_org", "Failed to delete organization"), "error");
  }

  async function saveBenchmarkProfile(benchmarkProfileId: string) {
    if (!selectedOrg) return;
    setSavingBenchmark(true);
    setError(null);
    const r = await apiFetch(`/organizations/${selectedOrg.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ benchmark_profile_id: benchmarkProfileId }),
    });
    if (r.ok) {
      const updated = await r.json();
      setSelectedOrg(updated);
      setOrgs((prev) => prev.map((org) => (org.id === updated.id ? updated : org)));
      const profilesResponse = await apiFetch(`/analytics/benchmarks/profiles?org_id=${selectedOrg.id}`);
      if (profilesResponse.ok) {
        setBenchmarkProfiles(await profilesResponse.json());
      }
      toast(tr("page.settings_organizations.toast.benchmark_saved", "Benchmark profile updated"), "success");
    } else {
      const d = await r.json().catch(() => ({}));
      const message = d.detail ?? tr("page.settings_organizations.error.save_benchmark", "Failed to save benchmark profile");
      setError(message);
      toast(message, "error");
    }
    setSavingBenchmark(false);
  }

  async function saveBenchmarkOverrides() {
    if (!selectedOrg || !selectedOrg.benchmark_profile_id) return;
    setSavingBenchmark(true);
    setError(null);

    const benchmarkProfileOverrides = {
      ...(selectedOrg.benchmark_profile_overrides ?? {}),
      profiles: {
        ...(selectedOrg.benchmark_profile_overrides?.profiles ?? {}),
        [selectedOrg.benchmark_profile_id]: {
          ...((selectedOrg.benchmark_profile_overrides?.profiles ?? {})[selectedOrg.benchmark_profile_id] ?? {}),
          rules: Object.fromEntries(
            Object.values(editingRules).map((rule) => [
              rule.id,
              {
                label: rule.label,
                threshold: Number(rule.threshold),
                priority: rule.priority,
                pass_text: rule.pass_text,
                fail_text: rule.fail_text,
              },
            ]),
          ),
        },
      },
    };

    const r = await apiFetch(`/organizations/${selectedOrg.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ benchmark_profile_overrides: benchmarkProfileOverrides }),
    });

    if (r.ok) {
      const updated = await r.json();
      setSelectedOrg(updated);
      setOrgs((prev) => prev.map((org) => (org.id === updated.id ? updated : org)));
      const profilesResponse = await apiFetch(`/analytics/benchmarks/profiles?org_id=${selectedOrg.id}`);
      if (profilesResponse.ok) {
        setBenchmarkProfiles(await profilesResponse.json());
      }
      toast(tr("page.settings_organizations.toast.overrides_saved", "Benchmark overrides saved"), "success");
    } else {
      const d = await r.json().catch(() => ({}));
      const message = d.detail ?? tr("page.settings_organizations.error.save_overrides", "Failed to save benchmark profile overrides");
      setError(message);
      toast(message, "error");
    }
    setSavingBenchmark(false);
  }

  function updateEditingRule(ruleId: string, field: keyof BenchmarkRule, value: string | number) {
    setEditingRules((prev) => ({
      ...prev,
      [ruleId]: {
        ...prev[ruleId],
        [field]: field === "threshold" ? Number(value) : value,
      },
    }));
  }

  const selectedProfile = useMemo(
    () => benchmarkProfiles.find((profile) => profile.id === (selectedOrg?.benchmark_profile_id ?? "")) ?? null,
    [benchmarkProfiles, selectedOrg],
  );

  const benchmarkSummary = useMemo(() => {
    if (!selectedProfile) return [];
    return [
      {
        label: tr("page.settings_organizations.benchmark_summary.profile", "Active profile"),
        value: selectedProfile.name,
      },
      {
        label: tr("page.settings_organizations.benchmark_summary.region", "Region"),
        value: selectedProfile.region || tr("common.none", "None"),
      },
      {
        label: tr("page.settings_organizations.benchmark_summary.rules", "Rules"),
        value: String(selectedProfile.rules_count),
      },
    ];
  }, [selectedProfile, tr]);

  const inputClass = "h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {tr("header.page.settings_organizations.title", "Organizations")}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {tr("header.page.settings_organizations.subtitle", "Manage multi-tenant workspaces and member access")}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
        >
          <span>+</span> {tr("page.settings_organizations.new_org", "New Organization")}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/30 dark:bg-red-900/10 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Org list */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            {tr("page.settings_organizations.your_orgs", "Your Organizations")}
          </h2>
          {loading ? (
            <div className="animate-pulse space-y-2">
              {[1, 2].map(i => <div key={i} className="h-20 rounded-xl bg-gray-100 dark:bg-gray-800" />)}
            </div>
          ) : orgs.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-200 p-8 text-center dark:border-gray-700">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {tr("page.settings_organizations.empty", "No organizations yet.")}
              </p>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                {tr("page.settings_organizations.empty_help", "Create the first workspace when you need separate benchmark rules, branding, or member access for another tenant.")}
              </p>
              <button
                onClick={() => setShowCreate(true)}
                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                <span>+</span> {tr("page.settings_organizations.new_org", "New Organization")}
              </button>
            </div>
          ) : (
            orgs.map(org => (
              <div
                key={org.id}
                onClick={() => setSelectedOrg(org)}
                className={`cursor-pointer rounded-xl border p-4 transition-all ${
                  selectedOrg?.id === org.id
                    ? "border-blue-300 bg-blue-50 shadow-sm dark:border-blue-700 dark:bg-blue-950/20"
                    : "border-gray-200 bg-white hover:border-gray-300 dark:border-gray-800 dark:bg-gray-900"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900 dark:text-white">{org.name}</span>
                      <PlanBadge plan={org.plan} />
                    </div>
                    <div className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                      /{org.slug} · {org.member_count}{" "}
                      {org.member_count === 1
                        ? tr("page.settings_organizations.member_label_singular", "member")
                        : tr("page.settings_organizations.member_label_plural", "members")}
                    </div>
                  </div>
                </div>
                {org.description && (
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{org.description}</p>
                )}
              </div>
            ))
          )}
        </div>

        {/* Org detail */}
        <div className="lg:col-span-2">
          {!selectedOrg ? (
            <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-400">
                {tr("page.settings_organizations.select_prompt", "Select an organization to manage it")}
              </p>
            </div>
          ) : (
            <div className="space-y-6 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white">{selectedOrg.name}</h3>
                  <div className="mt-1 flex items-center gap-3">
                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs dark:bg-gray-800">/{selectedOrg.slug}</code>
                    <PlanBadge plan={selectedOrg.plan} />
                  </div>
                  {selectedOrg.description && (
                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{selectedOrg.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => switchOrg(selectedOrg.id)}
                    className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-400"
                  >
                    {tr("page.settings_organizations.switch_org", "Switch to this org")}
                  </button>
                  <button
                    onClick={() => deleteOrg(selectedOrg.id)}
                    className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 dark:border-red-900/30 dark:bg-red-900/10 dark:text-red-400"
                  >
                    {tr("common.delete", "Delete")}
                  </button>
                </div>
              </div>

              <div className="space-y-4 rounded-xl border border-gray-100 p-4 dark:border-gray-800">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                      {tr("page.settings_organizations.benchmark.title", "Benchmark Profile")}
                    </h4>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {tr("page.settings_organizations.benchmark.help", "Choose the default institutional benchmark profile for this tenant.")}
                    </p>
                  </div>
                  <div className="min-w-[260px]">
                    <select
                      value={selectedOrg.benchmark_profile_id ?? ""}
                      onChange={(e) => saveBenchmarkProfile(e.target.value)}
                      disabled={savingBenchmark}
                      className={inputClass}
                    >
                      {benchmarkProfiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name}
                        </option>
                      ))}
                    </select>
                    {!benchmarkProfiles.length && (
                      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        {tr("page.settings_organizations.benchmark.empty", "No benchmark profiles available yet.")}
                      </p>
                    )}
                    {selectedProfile && (
                      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        {selectedProfile.description}
                      </p>
                    )}
                  </div>
                </div>
                {selectedProfile && (
                  <div className="grid gap-3 md:grid-cols-3">
                    {benchmarkSummary.map((item) => (
                      <div
                        key={item.label}
                        className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-950/40"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                          {item.label}
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          <p className="text-sm font-semibold text-gray-900 dark:text-white">{item.value}</p>
                          {item.label === tr("page.settings_organizations.benchmark_summary.profile", "Active profile") && selectedProfile.is_default && (
                            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                              {tr("page.settings_organizations.benchmark.default_badge", "Default")}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {selectedOrg.benchmark_profile_id && Object.values(editingRules).length > 0 && (
                  <div className="space-y-3 rounded-xl bg-gray-50 p-4 dark:bg-gray-950/40">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <h5 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                          {tr("page.settings_organizations.benchmark.overrides_title", "Rule overrides")}
                        </h5>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          {tr("page.settings_organizations.benchmark.overrides_help", "Adjust thresholds and copy for this tenant. The dashboard and briefs will inherit these values.")}
                        </p>
                      </div>
                      <button
                        onClick={saveBenchmarkOverrides}
                        disabled={savingBenchmark}
                        className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {savingBenchmark
                          ? tr("page.settings_organizations.saving", "Saving...")
                          : tr("page.settings_organizations.benchmark.save_overrides", "Save overrides")}
                      </button>
                    </div>
                    <div className="space-y-3">
                      {Object.values(editingRules).map((rule) => (
                        <div key={rule.id} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
                          <div className="grid gap-3 lg:grid-cols-[1.2fr,120px,140px]">
                          <div>
                              <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
                                {tr("page.settings_organizations.benchmark.rule_label", "Rule label")}
                              </label>
                              <input
                                value={rule.label}
                                onChange={(e) => updateEditingRule(rule.id, "label", e.target.value)}
                                className={inputClass}
                              />
                            </div>
                            <div>
                              <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
                                {tr("page.settings_organizations.benchmark.threshold", "Threshold")}
                              </label>
                              <input
                                type="number"
                                value={rule.threshold}
                                onChange={(e) => updateEditingRule(rule.id, "threshold", e.target.value)}
                                className={inputClass}
                              />
                            </div>
                            <div>
                              <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
                                {tr("page.settings_organizations.benchmark.priority", "Priority")}
                              </label>
                              <select
                                value={rule.priority}
                                onChange={(e) => updateEditingRule(rule.id, "priority", e.target.value)}
                                className={inputClass}
                              >
                                <option value="high">{tr("page.settings_organizations.priority.high", "High")}</option>
                                <option value="medium">{tr("page.settings_organizations.priority.medium", "Medium")}</option>
                                <option value="low">{tr("page.settings_organizations.priority.low", "Low")}</option>
                              </select>
                            </div>
                          </div>
                          <div className="mt-3 grid gap-3 lg:grid-cols-2">
                            <div>
                              <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
                                {tr("page.settings_organizations.benchmark.pass_message", "Pass message")}
                              </label>
                              <textarea
                                value={rule.pass_text}
                                onChange={(e) => updateEditingRule(rule.id, "pass_text", e.target.value)}
                                rows={2}
                                className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                              />
                            </div>
                            <div>
                              <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
                                {tr("page.settings_organizations.benchmark.fail_message", "Fail message")}
                              </label>
                              <textarea
                                value={rule.fail_text}
                                onChange={(e) => updateEditingRule(rule.id, "fail_text", e.target.value)}
                                rows={2}
                                className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                              />
                            </div>
                          </div>
                          <p className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
                            {tr("page.settings_organizations.benchmark.metric", "Metric")}: {rule.metric}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Members */}
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                    {tr("page.settings_organizations.members", "Members")} ({members.length})
                  </h4>
                  <button
                    onClick={() => setShowInvite(true)}
                    className="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                  >
                    + {tr("page.settings_organizations.invite", "Invite")}
                  </button>
                </div>
                {members.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center dark:border-gray-800">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {tr("page.settings_organizations.members_empty", "No members added yet")}
                    </p>
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                      {tr("page.settings_organizations.members_empty_help", "Invite an admin or collaborator when this workspace needs shared ownership or review.")}
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-100 dark:divide-gray-800 dark:border-gray-800">
                    {members.map(m => (
                      <div key={m.user_id} className="flex items-center justify-between px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                            {m.username.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-gray-900 dark:text-white">{m.display_name}</div>
                            <div className="text-xs text-gray-500">@{m.username}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                            m.role === "owner" ? "bg-amber-100 text-amber-700" :
                            m.role === "admin" ? "bg-blue-100 text-blue-700" :
                            "bg-gray-100 text-gray-600"
                          }`}>{tr(`page.settings_organizations.role.${m.role}`, m.role)}</span>
                          {m.role !== "owner" && (
                            <button
                              onClick={() => removeMember(m.user_id)}
                              className="rounded p-1 text-gray-400 hover:text-red-500"
                              title={tr("common.remove", "Remove")}
                            >
                              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create org modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-gray-900">
            <h3 className="mb-4 text-lg font-bold text-gray-900 dark:text-white">
              {tr("page.settings_organizations.new_org", "New Organization")}
            </h3>
            <div className="space-y-3">
              <input placeholder={tr("page.settings_organizations.form.name", "Organization name")} value={form.name} onChange={e => setForm({...form, name: e.target.value, slug: e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")})} className={inputClass} />
              <input placeholder={tr("page.settings_organizations.form.slug", "Slug (e.g. my-org)")} value={form.slug} onChange={e => setForm({...form, slug: e.target.value})} className={inputClass} />
              <textarea placeholder={tr("page.settings_organizations.form.description", "Description (optional)")} value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={2} className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white" />
              <select value={form.plan} onChange={e => setForm({...form, plan: e.target.value})} className={inputClass}>
                <option value="free">{tr("page.settings_organizations.plan.free", "Free")}</option>
                <option value="pro">{tr("page.settings_organizations.plan.pro", "Pro")}</option>
                <option value="enterprise">{tr("page.settings_organizations.plan.enterprise", "Enterprise")}</option>
              </select>
            </div>
            {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
            <div className="mt-4 flex gap-2">
              <button onClick={createOrg} disabled={saving || !form.name || !form.slug} className="flex-1 rounded-xl bg-blue-600 py-2.5 text-sm font-semibold text-white disabled:opacity-50 hover:bg-blue-700">
                {saving ? tr("page.settings_organizations.creating", "Creating…") : tr("common.create", "Create")}
              </button>
              <button onClick={() => { setShowCreate(false); setError(null); }} className="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-300">
                {tr("common.cancel", "Cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Invite modal */}
      {showInvite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl dark:bg-gray-900">
            <h3 className="mb-4 text-lg font-bold text-gray-900 dark:text-white">
              {tr("page.settings_organizations.invite_member", "Invite Member")}
            </h3>
            <div className="space-y-3">
              <input placeholder={tr("settings.account.username", "Username")} value={inviteForm.username} onChange={e => setInviteForm({...inviteForm, username: e.target.value})} className={inputClass} />
              <select value={inviteForm.role} onChange={e => setInviteForm({...inviteForm, role: e.target.value})} className={inputClass}>
                <option value="member">{tr("page.settings_organizations.role.member", "Member")}</option>
                <option value="admin">{tr("page.settings_organizations.role.admin", "Admin")}</option>
              </select>
            </div>
            {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
            <div className="mt-4 flex gap-2">
              <button onClick={inviteMember} disabled={saving || !inviteForm.username} className="flex-1 rounded-xl bg-blue-600 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                {saving ? tr("page.settings_organizations.inviting", "Inviting…") : tr("page.settings_organizations.invite", "Invite")}
              </button>
              <button onClick={() => { setShowInvite(false); setError(null); }} className="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm font-semibold dark:border-gray-700">
                {tr("common.cancel", "Cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
