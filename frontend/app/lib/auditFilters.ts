/** Filters of the audit log view, and the query they send (issue 378). */

export type AppliedFilters = {
  action: string; resource: string; user: string; ip: string; from: string; to: string; assistantOnly: boolean;
};

export const NO_FILTERS: AppliedFilters = {
  action: "", resource: "", user: "", ip: "", from: "", to: "", assistantOnly: false,
};

/**
 * The query parameters for a set of applied filters.
 *
 * The list, the CSV export and the Assistant's export action all describe the
 * same view, so they share one builder; three copies had already been kept in
 * step by hand, and a filter added to one but not another would export
 * something other than what is on screen.
 */
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
  if (filters.from) params.set("from_date", filters.from);
  if (filters.to) params.set("to_date", filters.to);
  return params;
}
