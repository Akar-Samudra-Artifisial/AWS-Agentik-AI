"use client";

import { ApprovalCard } from "@/components/ApprovalCard";
import { Card, EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/ui";
import { errorMessage, useApprovals } from "@/lib/api";

export default function ApprovalsPage() {
  const pending = useApprovals("pending");
  const all = useApprovals();
  const history = (all.data ?? [])
    .filter((a) => a.status !== "pending")
    .sort((a, b) => (b.decided_at ?? b.requested_at).localeCompare(a.decided_at ?? a.requested_at));

  const refresh = () => {
    void pending.mutate();
    void all.mutate();
  };

  return (
    <>
      <PageHeader
        title="Approval"
        description="Refund di atas batas otomatis membutuhkan keputusan staf. Agen melanjutkan kasus setelah Anda memutuskan."
      />

      <section aria-labelledby="pending-h">
        <h2 id="pending-h" className="mb-3 text-[15px] font-semibold text-stone-900">
          Menunggu keputusan {pending.data ? <span className="text-stone-500">({pending.data.length})</span> : null}
        </h2>
        {pending.error ? (
          <Card>
            <ErrorState message={errorMessage(pending.error)} onRetry={() => pending.mutate()} />
          </Card>
        ) : !pending.data ? (
          <Card>
            <LoadingRows rows={3} label="Memuat approval…" />
          </Card>
        ) : pending.data.length === 0 ? (
          <Card>
            <EmptyState title="Antrean kosong" hint="Tidak ada refund yang menunggu persetujuan." />
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
        <h2 id="history-h" className="mb-3 text-[15px] font-semibold text-stone-900">Riwayat</h2>
        {all.error ? (
          <Card>
            <ErrorState message={errorMessage(all.error)} onRetry={() => all.mutate()} />
          </Card>
        ) : !all.data ? (
          <Card>
            <LoadingRows rows={3} />
          </Card>
        ) : history.length === 0 ? (
          <Card>
            <EmptyState title="Belum ada riwayat keputusan" />
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
