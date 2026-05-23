import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import ReviewQueueControls from "../app/authority/ReviewQueueControls";
import { LanguageProvider } from "../app/contexts/LanguageContext";

function renderControls() {
  const onApplyInstitutionReconciliation = vi.fn();
  render(
    <LanguageProvider>
      <ReviewQueueControls
        activeDomain={null}
        queueMode="institutions"
        statusFilter="pending"
        fieldFilter=""
        authorRouteFilter=""
        authorReviewFilter="required"
        authorNilOnly={false}
        batchField=""
        batchEntityType="general"
        batchLimit={25}
        resolving={false}
        resolveResult={null}
        acting={false}
        selectedCount={0}
        summary={null}
        onQueueModeChange={vi.fn()}
        onStatusFilterChange={vi.fn()}
        onFieldFilterChange={vi.fn()}
        onAuthorRouteFilterChange={vi.fn()}
        onAuthorReviewFilterChange={vi.fn()}
        onAuthorNilOnlyChange={vi.fn()}
        onBatchFieldChange={vi.fn()}
        onBatchEntityTypeChange={vi.fn()}
        onBatchLimitChange={vi.fn()}
        onBatchResolve={vi.fn()}
        onApplyInstitutionReconciliation={onApplyInstitutionReconciliation}
        onBulkAction={vi.fn()}
      />
    </LanguageProvider>
  );
  return { onApplyInstitutionReconciliation };
}

describe("Authority institution queue", () => {
  it("renders the ROR reconciliation action", () => {
    localStorage.setItem("app_lang", "en");
    const { onApplyInstitutionReconciliation } = renderControls();

    fireEvent.click(screen.getByRole("button", { name: "Apply ROR reconciliation" }));

    expect(screen.getByText("Institution Queue")).toBeInTheDocument();
    expect(screen.getByText("ROR review queue")).toBeInTheDocument();
    expect(onApplyInstitutionReconciliation).toHaveBeenCalledTimes(1);
  });
});
