"use client";

import useSWR, { type SWRConfiguration } from "swr";
import type {
  ApprovalStatus,
  ApprovalWithCase,
  ApiErrorBody,
  CaseDetail,
  CaseStatus,
  CaseSummary,
  Channel,
  DecisionRequest,
  DecisionResponse,
  DemoResetResponse,
  HealthResponse,
  Metrics,
  SimulateInboundRequest,
  SimulateInboundResponse,
} from "./api-types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/+$/, "");
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export const POLL_MS = 3000;
export const isApiConfigured = BASE_URL.length > 0;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!isApiConfigured) {
    throw new ApiError(0, "not_configured", "NEXT_PUBLIC_API_BASE_URL belum diatur saat build.");
  }
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(API_KEY ? { "x-api-key": API_KEY } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "network", "Tidak dapat terhubung ke API.");
  }
  const text = await res.text();
  const body: unknown = text ? safeJson(text) : null;
  if (!res.ok) {
    const err = (body as Partial<ApiErrorBody> | null)?.error;
    throw new ApiError(res.status, err?.code ?? `http_${res.status}`, err?.message ?? res.statusText);
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

const fetcher = <T>(path: string) => request<T>(path);

const pollConfig: SWRConfiguration = {
  refreshInterval: POLL_MS,
  refreshWhenHidden: false,
  revalidateOnFocus: true,
  keepPreviousData: true,
};

function qs(params: Record<string, string | number | undefined>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") s.set(k, String(v));
  }
  const str = s.toString();
  return str ? `?${str}` : "";
}

export function useHealth() {
  return useSWR<HealthResponse>(isApiConfigured ? "/health" : null, fetcher, {
    refreshInterval: 10000,
    shouldRetryOnError: false,
  });
}

export function useMetrics() {
  return useSWR<Metrics>(isApiConfigured ? "/metrics" : null, fetcher, pollConfig);
}

export function useCases(filter: { status?: CaseStatus | ""; channel?: Channel | ""; limit?: number } = {}) {
  const key = `/cases${qs({ status: filter.status, channel: filter.channel, limit: filter.limit ?? 50 })}`;
  return useSWR<CaseSummary[]>(isApiConfigured ? key : null, fetcher, pollConfig);
}

export function useCase(caseId: string | null) {
  return useSWR<CaseDetail>(
    isApiConfigured && caseId ? `/cases/${encodeURIComponent(caseId)}` : null,
    fetcher,
    pollConfig,
  );
}

export function useApprovals(status?: ApprovalStatus) {
  const key = `/approvals${qs({ status })}`;
  return useSWR<ApprovalWithCase[]>(isApiConfigured ? key : null, fetcher, pollConfig);
}

export function decideApproval(approvalId: string, body: DecisionRequest) {
  return request<DecisionResponse>(`/approvals/${encodeURIComponent(approvalId)}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function simulateInbound(body: SimulateInboundRequest) {
  return request<SimulateInboundResponse>("/simulate/inbound", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function resetDemo() {
  return request<DemoResetResponse>("/demo/reset", { method: "POST" });
}

export function fetchCases(limit = 20) {
  return request<CaseSummary[]>(`/cases${qs({ limit })}`);
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401 || err.status === 403) return "API key ditolak (401/403). Periksa NEXT_PUBLIC_API_KEY.";
    if (err.status === 404) return "Data tidak ditemukan (404).";
    if (err.status === 0) return err.message;
    return `${err.message} (HTTP ${err.status})`;
  }
  return err instanceof Error ? err.message : "Terjadi kesalahan tak terduga.";
}

export const STAFF_NAME = process.env.NEXT_PUBLIC_STAFF_NAME || "Supervisor";
export const DEMO_PHONE_E164 = process.env.NEXT_PUBLIC_DEMO_PHONE_E164 ?? "";
export const DEMO_CUSTOMER_NAME = process.env.NEXT_PUBLIC_DEMO_CUSTOMER_NAME || "Pelanggan demo";
