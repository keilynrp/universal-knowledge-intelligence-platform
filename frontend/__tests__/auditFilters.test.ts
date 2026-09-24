import { filterParams, NO_FILTERS } from "../app/lib/auditFilters";

test("no filters send no parameters", () => {
    expect(filterParams(NO_FILTERS).toString()).toBe("");
});

test("an address filter is sent as ip_address", () => {
    const params = filterParams({ ...NO_FILTERS, ip: "203.0.113.7" });
    expect(Object.fromEntries(params)).toEqual({ ip_address: "203.0.113.7" });
});

test("every filter reaches the query, so the export matches what is on screen", () => {
    const params = filterParams({
        action: "DELETE",
        resource: "entity",
        user: "alice",
        ip: "2001:db8::1",
        from: "2026-09-22T00:00",
        to: "2026-09-23T00:00",
        assistantOnly: false,
    });
    expect(Object.fromEntries(params)).toEqual({
        action: "DELETE",
        resource_type: "entity",
        username: "alice",
        ip_address: "2001:db8::1",
        from_date: "2026-09-22T00:00",
        to_date: "2026-09-23T00:00",
    });
});

test("assistant-only overrides action and resource but keeps the address", () => {
    const params = filterParams({ ...NO_FILTERS, action: "DELETE", resource: "entity", ip: "203.0.113.7", assistantOnly: true });
    expect(Object.fromEntries(params)).toEqual({
        action: "ASSISTANT_ACTION",
        resource_type: "assistant_action",
        ip_address: "203.0.113.7",
    });
});
