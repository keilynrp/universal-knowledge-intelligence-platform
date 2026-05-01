import "@testing-library/jest-dom";

const stableSearchParams = new URLSearchParams();

// Mock next/link — render a plain <a> in tests
vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => stableSearchParams,
}));

// Suppress noisy console.error from React in tests
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    if (
      typeof args[0] === "string" &&
      (args[0].includes("Warning:") || args[0].includes("act("))
    ) return;
    originalError(...args);
  };
});
afterAll(() => {
  console.error = originalError;
});
