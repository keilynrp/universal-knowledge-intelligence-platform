import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import SessionList, { type SessionItem } from "../app/components/SessionList";
import { LanguageProvider } from "../app/contexts/LanguageContext";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
import { apiFetch } from "@/lib/api";

const mockFetch = apiFetch as ReturnType<typeof vi.fn>;

const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";
const LAPTOP = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

function session(id: number, overrides: Partial<SessionItem> = {}): SessionItem {
    return {
        id,
        sid: `sid-${id}`,
        created_at: "2026-09-20T10:00:00Z",
        last_seen_at: "2026-09-23T10:00:00Z",
        expires_at: "2026-09-30T10:00:00Z",
        user_agent: LAPTOP,
        ip_address: "203.0.113.7",
        current: false,
        ...overrides,
    };
}

function ok(body: unknown) {
    return { ok: true, status: 200, json: async () => body };
}

function renderList(props: Partial<Parameters<typeof SessionList>[0]> = {}) {
    const toast = vi.fn();
    render(
        <LanguageProvider>
            <SessionList endpoint="/auth/sessions" scope="self" toast={toast} {...props} />
        </LanguageProvider>,
    );
    return { toast };
}

beforeEach(() => {
    localStorage.setItem("app_lang", "en");
    mockFetch.mockReset();
});

test("marks the current session and offers no way to revoke it", async () => {
    mockFetch.mockResolvedValue(ok({ items: [session(1, { current: true, user_agent: IPHONE }), session(2)] }));
    renderList();

    const current = (await screen.findByText("Safari on iOS")).closest("li")!;
    expect(within(current).getByText("This device")).toBeInTheDocument();
    expect(within(current).queryByRole("button", { name: /revoke/i })).toBeNull();

    const other = screen.getByText("Chrome on Linux").closest("li")!;
    expect(within(other).getByRole("button", { name: "Revoke session: Chrome on Linux" })).toBeInTheDocument();
    expect(within(other).getByText(/IP 203\.0\.113\.7/)).toBeInTheDocument();
});

test("revoking one session asks first, then deletes exactly that one", async () => {
    mockFetch
        .mockResolvedValueOnce(ok({ items: [session(1, { current: true }), session(2)] }))
        .mockResolvedValueOnce(ok({ revoked: 1, id: 2 }))
        .mockResolvedValueOnce(ok({ items: [session(1, { current: true })] }));
    const { toast } = renderList();

    fireEvent.click(await screen.findByRole("button", { name: "Revoke session: Chrome on Linux" }));
    expect(mockFetch).toHaveBeenCalledTimes(1); // nothing sent before confirming

    const confirm = screen.getByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: "Revoke" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith("Session revoked", "success"));
    expect(mockFetch).toHaveBeenNthCalledWith(2, "/auth/sessions/2", { method: "DELETE" });
    await waitFor(() => expect(screen.queryByText("Active sessions: 2")).toBeNull());
    expect(screen.getByText("Active sessions: 1")).toBeInTheDocument();
});

test("cancelling a confirmation sends nothing", async () => {
    mockFetch.mockResolvedValue(ok({ items: [session(1, { current: true }), session(2)] }));
    renderList();

    fireEvent.click(await screen.findByRole("button", { name: "Revoke session: Chrome on Linux" }));
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(mockFetch).toHaveBeenCalledTimes(1);
});

test("signing out everywhere else hits the bulk endpoint and reports the count", async () => {
    mockFetch
        .mockResolvedValueOnce(ok({ items: [session(1, { current: true }), session(2), session(3)] }))
        .mockResolvedValueOnce(ok({ revoked: 2 }))
        .mockResolvedValueOnce(ok({ items: [session(1, { current: true })] }));
    const { toast } = renderList();

    fireEvent.click(await screen.findByRole("button", { name: "Sign out everywhere else" }));
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Sign out everywhere else" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith("Sessions revoked: 2", "success"));
    expect(mockFetch).toHaveBeenNthCalledWith(2, "/auth/sessions", { method: "DELETE" });
});

test("with only the current session there is nothing else to sign out", async () => {
    mockFetch.mockResolvedValue(ok({ items: [session(1, { current: true })] }));
    renderList();

    expect(await screen.findByRole("button", { name: "Sign out everywhere else" })).toBeDisabled();
});

test("an admin list can revoke every session, since none of them is this browser", async () => {
    mockFetch.mockResolvedValue(ok({ items: [session(4), session(5, { user_agent: null, ip_address: null })] }));
    renderList({ endpoint: "/users/9/sessions", scope: "admin", username: "alice" });

    expect(await screen.findByRole("button", { name: "Revoke all sessions" })).toBeEnabled();
    expect(screen.getAllByRole("button", { name: /^Revoke session:/ })).toHaveLength(2);
    expect(screen.getByText("Unknown device")).toBeInTheDocument();
    expect(screen.queryByText("This device")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Revoke all sessions" }));
    expect(screen.getByRole("alertdialog")).toHaveAccessibleName(
        "Sign alice out of every device? The account stays active and can sign in again.",
    );
});

test("a failed revoke is reported and the list is reloaded rather than trusted", async () => {
    mockFetch
        .mockResolvedValueOnce(ok({ items: [session(1, { current: true }), session(2)] }))
        .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: "Session not found" }) })
        .mockResolvedValueOnce(ok({ items: [session(1, { current: true })] }));
    const { toast } = renderList();

    fireEvent.click(await screen.findByRole("button", { name: "Revoke session: Chrome on Linux" }));
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Revoke" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith("Session not found", "error"));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(3));
});

test("a failed load says so and can be retried", async () => {
    mockFetch
        .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) })
        .mockResolvedValueOnce(ok({ items: [session(1, { current: true })] }));
    renderList();

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load sessions");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("This device")).toBeInTheDocument();
});
