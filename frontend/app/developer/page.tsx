"use client";

import { useState } from "react";
import { PageHeader } from "../components/ui";

// ── Constants ──────────────────────────────────────────────────────────────────

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SWAGGER_URL  = `${API_BASE}/docs`;
const REDOC_URL    = `${API_BASE}/redoc`;
const OPENAPI_URL  = `${API_BASE}/openapi.json`;

// ── Tag groups ─────────────────────────────────────────────────────────────────

const TAG_GROUPS = [
  {
    group: "Core",
    color: "blue",
    tags: [
      { name: "auth",      description: "Login & token (OAuth2 password flow)" },
      { name: "users",     description: "User management and role-based access" },
      { name: "entities",  description: "Entity CRUD, enrichment, Monte-Carlo scoring" },
      { name: "ingestion", description: "CSV / Excel / BibTeX / RIS upload and export" },
    ],
  },
  {
    group: "Knowledge",
    color: "violet",
    tags: [
      { name: "domains",         description: "Domain registry and OLAP cube" },
      { name: "harmonization",   description: "Multi-step data-cleaning pipeline" },
      { name: "disambiguation",  description: "Cluster detection and normalization rules" },
      { name: "authority",       description: "Wikidata / VIAF / ORCID / OpenAlex linking" },
    ],
  },
  {
    group: "Insights",
    color: "emerald",
    tags: [
      { name: "analytics",  description: "KPI dashboard, domain compare, topic modeling" },
      { name: "ai-rag",     description: "AI integrations and RAG vector search" },
      { name: "reports",    description: "Report builder, PDF/Excel exports" },
      { name: "search",     description: "Full-text search" },
    ],
  },
  {
    group: "Platform",
    color: "amber",
    tags: [
      { name: "stores",            description: "Store connectors and sync queue" },
      { name: "webhooks",          description: "Outbound webhook subscriptions" },
      { name: "scheduled-imports", description: "Cron-style import schedules" },
      { name: "audit",             description: "Immutable audit log" },
    ],
  },
];

const COLOR_MAP: Record<string, string> = {
  blue:   "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-800",
  violet: "bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-800",
  emerald:"bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-800",
  amber:  "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-800",
};

// ── Quick-start steps ──────────────────────────────────────────────────────────

const QUICKSTART = [
  {
    step: 1,
    title: "Get a token",
    language: "bash",
    code: `curl -X POST "${API_BASE}/auth/token" \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "username=admin&password=changeit"`,
  },
  {
    step: 2,
    title: "Use the token",
    language: "bash",
    code: `TOKEN="<paste access_token here>"

# List entities
curl "${API_BASE}/entities?limit=20" \\
  -H "Authorization: Bearer $TOKEN"`,
  },
  {
    step: 3,
    title: "Upload a CSV",
    language: "bash",
    code: `curl -X POST "${API_BASE}/upload" \\
  -H "Authorization: Bearer $TOKEN" \\
  -F "file=@your_data.csv"`,
  },
  {
    step: 4,
    title: "BibTeX import",
    language: "bash",
    code: `curl -X POST "${API_BASE}/upload" \\
  -H "Authorization: Bearer $TOKEN" \\
  -F "file=@references.bib"
# Returns format="bibtex", domain="science"`,
  },
];

// ── SDK snippets ───────────────────────────────────────────────────────────────

const SDK_SNIPPETS = [
  {
    lang: "Python",
    code: `import requests

BASE = "${API_BASE}"

# 1 — authenticate
token = requests.post(
    f"{BASE}/auth/token",
    data={"username": "admin", "password": "changeit"},
).json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# 2 — fetch entities
entities = requests.get(f"{BASE}/entities", headers=headers).json()
print(entities)`,
  },
  {
    lang: "TypeScript",
    code: `const BASE = "${API_BASE}";

// 1 — authenticate
const form = new URLSearchParams({ username: "admin", password: "changeit" });
const { access_token } = await fetch(\`\${BASE}/auth/token\`, {
  method: "POST",
  body: form,
}).then((r) => r.json());

const headers = { Authorization: \`Bearer \${access_token}\` };

// 2 — fetch entities
const entities = await fetch(\`\${BASE}/entities\`, { headers }).then((r) => r.json());
console.log(entities);`,
  },
];

// ── CopyButton ─────────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
      }}
      className="rounded px-2 py-0.5 text-xs font-medium transition-colors bg-gray-700 text-gray-300 hover:bg-gray-600"
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

// ── CodeBlock ──────────────────────────────────────────────────────────────────

function CodeBlock({ code, label }: { code: string; label?: string }) {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-800 bg-gray-950">
      {label && (
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
          <span className="text-xs font-medium text-gray-400">{label}</span>
          <CopyButton text={code} />
        </div>
      )}
      {!label && (
        <div className="flex justify-end px-4 py-2 border-b border-gray-800">
          <CopyButton text={code} />
        </div>
      )}
      <pre className="overflow-x-auto p-4 text-xs leading-relaxed text-gray-300">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function DeveloperPortalPage() {
  const [activeSDK, setActiveSDK] = useState(0);

  return (
    <div className="space-y-8">
      <PageHeader
        breadcrumbs={[
          { label: "Home", href: "/" },
          { label: "Developer Portal" },
        ]}
        title="Developer Portal"
        description="API reference, quick-start guides, and client SDK examples"
      />

      {/* ── Doc links ── */}
      <div className="grid gap-4 sm:grid-cols-3">
        <a
          href={SWAGGER_URL}
          target="_blank"
          rel="noreferrer"
          className="group flex flex-col gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-5 shadow-sm transition-shadow hover:shadow-md dark:border-blue-800 dark:bg-blue-500/5"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white text-lg font-bold">S</div>
            <div>
              <p className="font-semibold text-blue-900 dark:text-blue-100">Swagger UI</p>
              <p className="text-xs text-blue-600 dark:text-blue-400">Interactive API explorer</p>
            </div>
          </div>
          <p className="text-sm text-blue-700 dark:text-blue-300">
            Try endpoints directly in your browser. Authenticate once and test any route.
          </p>
          <span className="mt-auto text-xs font-medium text-blue-600 group-hover:underline dark:text-blue-400">
            Open Swagger UI →
          </span>
        </a>

        <a
          href={REDOC_URL}
          target="_blank"
          rel="noreferrer"
          className="group flex flex-col gap-3 rounded-2xl border border-violet-200 bg-violet-50 p-5 shadow-sm transition-shadow hover:shadow-md dark:border-violet-800 dark:bg-violet-500/5"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600 text-white text-lg font-bold">R</div>
            <div>
              <p className="font-semibold text-violet-900 dark:text-violet-100">ReDoc</p>
              <p className="text-xs text-violet-600 dark:text-violet-400">Readable reference docs</p>
            </div>
          </div>
          <p className="text-sm text-violet-700 dark:text-violet-300">
            Clean, three-panel documentation view ideal for reading and sharing.
          </p>
          <span className="mt-auto text-xs font-medium text-violet-600 group-hover:underline dark:text-violet-400">
            Open ReDoc →
          </span>
        </a>

        <a
          href={OPENAPI_URL}
          target="_blank"
          rel="noreferrer"
          download="ukip-openapi.json"
          className="group flex flex-col gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm transition-shadow hover:shadow-md dark:border-emerald-800 dark:bg-emerald-500/5"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white text-lg font-bold">{"{ }"}</div>
            <div>
              <p className="font-semibold text-emerald-900 dark:text-emerald-100">OpenAPI JSON</p>
              <p className="text-xs text-emerald-600 dark:text-emerald-400">Machine-readable spec</p>
            </div>
          </div>
          <p className="text-sm text-emerald-700 dark:text-emerald-300">
            Download the raw OpenAPI 3.1 spec to generate clients in any language.
          </p>
          <span className="mt-auto text-xs font-medium text-emerald-600 group-hover:underline dark:text-emerald-400">
            Download openapi.json →
          </span>
        </a>
      </div>

      {/* ── Auth info ── */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-800 dark:bg-amber-500/5">
        <h3 className="mb-2 text-sm font-semibold text-amber-900 dark:text-amber-100">Authentication</h3>
        <p className="text-sm text-amber-800 dark:text-amber-300">
          All endpoints (except <code className="rounded bg-amber-100 px-1 py-0.5 text-xs dark:bg-amber-900">/health</code> and{" "}
          <code className="rounded bg-amber-100 px-1 py-0.5 text-xs dark:bg-amber-900">/auth/token</code>) require a Bearer JWT token.
          Use the <strong>Authorize</strong> button in Swagger UI to persist your token across requests.
          Tokens expire after <strong>8 hours</strong> — re-authenticate when needed.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {["viewer", "editor", "admin", "super_admin"].map((role) => (
            <span
              key={role}
              className="rounded-full bg-amber-100 px-3 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/50 dark:text-amber-200"
            >
              {role}
            </span>
          ))}
        </div>
      </div>

      {/* ── Quick-start ── */}
      <div>
        <h2 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">Quick Start (cURL)</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {QUICKSTART.map((qs) => (
            <div key={qs.step} className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400">
                Step {qs.step} — {qs.title}
              </p>
              <CodeBlock code={qs.code} />
            </div>
          ))}
        </div>
      </div>

      {/* ── SDK snippets ── */}
      <div>
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Client SDK Examples</h2>
          <div className="flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 dark:border-gray-700 dark:bg-gray-800">
            {SDK_SNIPPETS.map((s, i) => (
              <button
                key={s.lang}
                onClick={() => setActiveSDK(i)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  activeSDK === i
                    ? "bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white"
                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                }`}
              >
                {s.lang}
              </button>
            ))}
          </div>
        </div>
        <CodeBlock code={SDK_SNIPPETS[activeSDK].code} label={SDK_SNIPPETS[activeSDK].lang} />
      </div>

      {/* ── Tag groups ── */}
      <div>
        <h2 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">Endpoint Groups</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {TAG_GROUPS.map((group) => {
            const cls = COLOR_MAP[group.color];
            return (
              <div
                key={group.group}
                className={`rounded-2xl p-4 ring-1 ${cls}`}
              >
                <p className="mb-3 text-xs font-bold uppercase tracking-wider">{group.group}</p>
                <div className="space-y-2">
                  {group.tags.map((tag) => (
                    <a
                      key={tag.name}
                      href={`${SWAGGER_URL}#/${tag.name}`}
                      target="_blank"
                      rel="noreferrer"
                      className="block"
                    >
                      <p className="text-xs font-semibold hover:underline">{tag.name}</p>
                      <p className="text-xs opacity-70">{tag.description}</p>
                    </a>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Rate limits & versioning ── */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Rate Limits</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400">
                <th className="pb-2 font-medium">Endpoint</th>
                <th className="pb-2 font-medium">Limit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {[
                { endpoint: "POST /auth/token", limit: "5 / min" },
                { endpoint: "All other endpoints", limit: "No enforced limit" },
              ].map((row) => (
                <tr key={row.endpoint}>
                  <td className="py-1.5 font-mono text-gray-700 dark:text-gray-300">{row.endpoint}</td>
                  <td className="py-1.5 text-gray-500">{row.limit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Common Headers</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400">
                <th className="pb-2 font-medium">Header</th>
                <th className="pb-2 font-medium">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {[
                { header: "Authorization: Bearer <token>", desc: "Required for protected routes" },
                { header: "X-Total-Count", desc: "Response: total items (GET /entities)" },
              ].map((row) => (
                <tr key={row.header}>
                  <td className="py-1.5 font-mono text-gray-700 dark:text-gray-300 break-all">{row.header}</td>
                  <td className="py-1.5 text-gray-500">{row.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
