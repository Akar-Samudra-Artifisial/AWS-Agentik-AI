/**
 * Tipe kontrak API ResolveAI, alias dari `api-types.gen.ts` yang dihasilkan
 * `openapi-typescript` dari snapshot OpenAPI backend (`npm run gen:types`).
 * Jangan edit file gen secara manual; tambahkan alias di sini.
 */
import type { components } from "./api-types.gen";

type Schemas = components["schemas"];

export type Channel = Schemas["Channel"];
export type CaseStatus = Schemas["CaseStatus"];
export type CaseCategory = Schemas["CaseCategory"];
export type Priority = Schemas["CasePriority"];
export type ResolutionType = Schemas["ResolutionType"];
export type OrderStatus = Schemas["OrderStatus"];
export type DeliveryStatus = Schemas["DeliveryStatus"];
export type MessageDirection = Schemas["MessageDirection"];
export type MessageAuthor = Schemas["MessageAuthor"];
export type AgentEventType = Schemas["AgentEventType"];
export type ApprovalStatus = Schemas["ApprovalStatus"];

export type Case = Schemas["Case"];
export type CaseSummary = Schemas["CaseSummary"];
export type Resolution = Schemas["CaseResolution"];
export type Customer = Schemas["Customer"];
export type OrderItem = Schemas["OrderItem"];
export type TrackingEvent = Schemas["TrackingEvent"];
export type Order = Schemas["Order"];
export type Message = Schemas["Message"];
export type AgentEvent = Schemas["AgentEvent"];
export type Approval = Schemas["Approval"];
/** Item `GET /approvals`: approval + ringkasan kasus (`case`) bila tersedia. */
export type ApprovalWithCase = Schemas["ApprovalWithCase"];
/** `GET /cases/{id}`: kasus bersarang di `case`, bukan di level atas. */
export type CaseDetail = Schemas["CaseDetail"];
export type Metrics = Schemas["Metrics"];
export type HealthResponse = Schemas["HealthResponse"];

/** Backend mengetik `decision` sebagai string bebas; dashboard hanya mengirim dua nilai ini. */
export type DecisionRequest = Omit<Schemas["DecisionRequest"], "decision"> & {
  decision: "approve" | "reject";
};
export type DecisionResponse = Schemas["DecisionResponse"];
export type SimulateInboundRequest = Schemas["SimulateInboundRequest"];
export type SimulateInboundResponse = Schemas["SimulateInboundResponse"];
export type DemoResetResponse = Schemas["DemoResetResponse"];
export type ApiErrorBody = Schemas["ErrorResponse"];
