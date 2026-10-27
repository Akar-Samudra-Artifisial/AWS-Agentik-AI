"use client";

import { ApprovalCard } from "@/components/ApprovalCard";
import { Card, EmptyState, ErrorState, LoadingRows, PageHeader, SectionHeading } from "@/components/ui";
import { errorMessage, useApprovals } from "@/lib/api";

export default function ApprovalsPage() {
  const pending = useApprovals("pending");
  // GET /approvals tanpa status = pending (default backend), jadi riwayat diambil per status.
  const approved = useApprovals("approved");
  const rejected = useApprovals("rejected");
  const historyError = approved.error ?? rejected.error;
  const historyLoaded = approved.data != null && rejected.data != null;
  const history = [...(approved.data ?? []), ...(rejected.data ?? [])].sort((a, b) =>
    (b.decided_at ?? b.requested_at).localeCompare(a.decided_at ?? a.requested_at),
  );

  const refreshHistory = () => {
    void approved.mutate();
    void rejected.mutate();
  };
  const refresh = () => {
    void pending.mutate();
    refreshHistory();
  };

  return (
    <>
      <PageHeader
        title="Approvals"
        description="Refunds above the auto-approval limit need a staff decision. The agent can’t pay out without one — it resumes the case as soon as you decide."
      />

      <section aria-labelledby="pending-h">
        <SectionHeading id="pending-h" title="Awaiting decision" count={pending.data?.length} />
        {pending.error ? (
          <Card>
            <ErrorState message={errorMessage(pending.error)} onRetry={() => pending.mutate()} />
          </Card>
        ) : !pending.data ? (
          <Card>
            <LoadingRows rows={3} label="Loading approvals…" />
          </Card>
        ) : pending.data.length === 0 ? (
          <Card>
            <EmptyState title="Queue is empty" hint="No refunds are waiting for approval." />
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {pending.data.map((a) => (
              <ApprovalCard key={a.approval_id} approval={a} onDecided={refresh} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="history-h" className="mt-10">
        <SectionHeading id="history-h" title="Decision history" count={historyLoaded ? history.length : undefined} />
        {historyError ? (
          <Card>
            <ErrorState message={errorMessage(historyError)} onRetry={refreshHistory} />
          </Card>
        ) : !historyLoaded ? (
          <Card>
            <LoadingRows rows={3} label="Loading history…" />
          </Card>
        ) : history.length === 0 ? (
          <Card>
            <EmptyState title="No decisions yet" hint="Approved and rejected refunds will be listed here." />
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {history.map((a) => (
              <ApprovalCard key={a.approval_id} approval={a} compact />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
