/** Filters of the audit log view, and the query they send (issues 378 and 375). */

export type AppliedFilters = {
  action: string; resource: string; user: string; ip: string; session: string;
  from: string; to: string; assistantOnly: boolean;
};

export const NO_FILTERS: AppliedFilters = {
  action: "", resource: "", user: "", ip: "", session: "", from: "", to: "", assistantOnly: false,
};

/**
 * The query parameters for a set of applied filters.
 *
 * The list, the CSV export and the Assistant's export action all describe the
 * same view, so they share one builder; three copies had already been kept in
 * step by hand, and a filter added to one but not another would export
 * something other than what is on screen.
 */
/**
 * The pivot filters a link can carry into the page (`/audit-log?session_id=…`),
 * read once when the page opens. Only the two incident pivots are accepted:
 * anything else in the URL is ignored rather than half-applied.
 */
export function pivotFromQuery(search: string): Partial<AppliedFilters> {
  const query = new URLSearchParams(search);
  const pivot: Partial<AppliedFilters> = {};
  const session = query.get("session_id")?.trim();
  const ip = query.get("ip_address")?.trim();
  if (session) pivot.session = session;
  if (ip) pivot.ip = ip;
  return pivot;
}

export function filterParams(filters: AppliedFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.assistantOnly) {
    params.set("action", "ASSISTANT_ACTION");
    params.set("resource_type", "assistant_action");
  } else {
    if (filters.action) params.set("action", filters.action);
    if (filters.resource) params.set("resource_type", filters.resource);
  }
  if (filters.user) params.set("username", filters.user);
  if (filters.ip) params.set("ip_address", filters.ip);
  if (filters.session) params.set("session_id", filters.session);
  if (filters.from) params.set("from_date", filters.from);
  if (filters.to) params.set("to_date", filters.to);
  return params;
}
