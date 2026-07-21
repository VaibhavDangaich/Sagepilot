export type ActionName =
  | "message_fulfillment_team"
  | "message_payments_team"
  | "message_logistics_team"
  | "message_customer"
  | "create_internal_note";

export const ALL_ACTIONS: ActionName[] = [
  "message_fulfillment_team",
  "message_payments_team",
  "message_logistics_team",
  "message_customer",
  "create_internal_note",
];

export type WakeAggressiveness = "conservative" | "balanced" | "aggressive";

export type OrderEventType =
  | "order_created"
  | "payment_confirmed"
  | "payment_failed"
  | "shipment_created"
  | "shipment_delayed"
  | "delivered"
  | "refund_requested"
  | "customer_message_received"
  | "no_update_for_n_hours";

export const ALL_EVENT_TYPES: OrderEventType[] = [
  "order_created",
  "payment_confirmed",
  "payment_failed",
  "shipment_created",
  "shipment_delayed",
  "delivered",
  "refund_requested",
  "customer_message_received",
  "no_update_for_n_hours",
];

export interface ModelConfig {
  provider: string;
  model: string;
  temperature: number;
}

export interface SupervisorConfig {
  id: string;
  name: string;
  base_instruction: string;
  available_actions: ActionName[];
  default_wake_policy: string;
  model_config: ModelConfig;
  wake_aggressiveness: WakeAggressiveness;
  max_workflow_age_hours: number | null;
}

export interface CreateSupervisorRequest {
  name: string;
  base_instruction: string;
  available_actions?: ActionName[];
  default_wake_policy?: string;
  model_config?: ModelConfig;
  wake_aggressiveness?: WakeAggressiveness;
  max_workflow_age_hours?: number | null;
}

export type RunStatus = "active" | "sleeping" | "paused" | "completed" | "terminated";

export interface RunSummary {
  id: string;
  supervisor_id: string;
  order_id: string;
  temporal_workflow_id: string;
  status: RunStatus;
  next_wake_at: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface RunDetail extends RunSummary {
  memory_summary: string;
  wake_policy: string;
  final_summary: string | null;
  final_learnings: string | null;
  final_feedback: string | null;
}

export interface CreateRunRequest {
  supervisor_id: string;
  order_id: string;
  initial_instruction?: string | null;
}

export type ActivityLogKind =
  | "incoming_event"
  | "wake_decision"
  | "sleep_decision"
  | "agent_action"
  | "manual_instruction"
  | "final_output"
  | "system";

export interface TimelineEntry {
  seq: number;
  kind: ActivityLogKind;
  payload: Record<string, unknown>;
  created_at: string;
}
