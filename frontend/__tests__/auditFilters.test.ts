import { filterParams, NO_FILTERS, pivotFromQuery } from "../app/lib/auditFilters";

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
        session: "sid-1",
        from: "2026-09-22T00:00",
        to: "2026-09-23T00:00",
        assistantOnly: false,
    });
    expect(Object.fromEntries(params)).toEqual({
        action: "DELETE",
        resource_type: "entity",
        username: "alice",
        ip_address: "2001:db8::1",
        session_id: "sid-1",
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

test("a session filter is sent as session_id", () => {
    expect(Object.fromEntries(filterParams({ ...NO_FILTERS, session: "sid-1" }))).toEqual({ session_id: "sid-1" });
});

test("a link can open the page on a session or an address, and nothing else", () => {
    expect(pivotFromQuery("?session_id=sid-1")).toEqual({ session: "sid-1" });
    expect(pivotFromQuery("?ip_address=203.0.113.7&session_id=%20")).toEqual({ ip: "203.0.113.7" });
    expect(pivotFromQuery("?action=DELETE&username=alice")).toEqual({});
    expect(pivotFromQuery("")).toEqual({});
});
