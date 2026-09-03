export type ElectronicTaxTypeCode = 33 | 34 | 56 | 61;

export type ElectronicTaxState =
  | 'DRAFT'
  | 'READY'
  | 'FOLIO_RESERVED'
  | 'SIGNED'
  | 'SUBMITTED'
  | 'PROCESSING'
  | 'ACCEPTED'
  | 'ACCEPTED_WITH_REPAIR'
  | 'REJECTED'
  | 'SEND_UNCERTAIN'
  | 'VOIDED_PRE_SUBMISSION'
  | 'CANCELLED_BY_REFERENCE'
  | 'DISCARDED';

export type ElectronicTaxReferenceReason =
  | 'CANCEL_DOCUMENT'
  | 'CORRECT_TEXT'
  | 'CANCEL_DEBIT_NOTE'
  | 'CANCEL_CREDIT_NOTE'
  | 'CORRECT_AMOUNTS';

export interface ElectronicTaxLine {
  id: number;
  line_number: number;
  variant: number | null;
  sku: string;
  description: string;
  quantity: string;
  unit_price: string;
  discount_amount: string;
  tax_category: string;
  net_amount: string;
  exempt_amount: string;
  vat_amount: string;
  total_amount: string;
}

export interface ElectronicTaxReference {
  id: number;
  referenced_document: number;
  reason: ElectronicTaxReferenceReason;
  reference_code: string;
  reference_date: string;
  referenced_type_code: ElectronicTaxTypeCode;
  referenced_folio: number | null;
  description: string;
  created_at: string;
}

export interface ElectronicTaxEvent {
  id: number;
  event_type: string;
  actor: number | null;
  correlation_id: string;
  normalized_code: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ElectronicTaxExchange {
  delivery_state: string;
  recipient_email: string;
  envelope_hash: string;
  ride_hash: string;
  send_attempts: number;
  last_send_error: string;
  sent_at: string | null;
  receiver_response_state: string;
  receiver_response_code: string;
  receiver_response_message: string;
  receiver_response_hash: string;
  receiver_response_at: string | null;
}

export interface ElectronicTaxDocument {
  id: number;
  company: number;
  branch: number;
  sale: number | null;
  type_code: ElectronicTaxTypeCode;
  state: ElectronicTaxState;
  version: number;
  issuer_rut: string;
  issuer_legal_name: string;
  issuer_business_activity: string;
  issuer_address: string;
  issuer_commune: string;
  issuer_city: string;
  issuer_tax_email: string;
  receiver_rut: string;
  receiver_legal_name: string;
  receiver_business_activity: string;
  receiver_address: string;
  receiver_commune: string;
  receiver_city: string;
  receiver_tax_email: string;
  net_amount: string;
  exempt_amount: string;
  vat_rate: string;
  vat_amount: string;
  total_amount: string;
  currency: string;
  issue_date: string | null;
  folio: number | null;
  provider_track_id: string;
  provider_status_code: string;
  provider_status_message: string;
  provider_last_checked_at: string | null;
  snapshot_hash: string;
  xml_hash: string;
  correlation_id: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  discarded_at: string | null;
  lines: ElectronicTaxLine[];
  references: ElectronicTaxReference[];
  events: ElectronicTaxEvent[];
  exchange: ElectronicTaxExchange | null;
}

export interface ElectronicTaxPagination {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ElectronicTaxListResponse {
  documents: ElectronicTaxDocument[];
  pagination: ElectronicTaxPagination;
}

export interface ElectronicTaxListQuery {
  branch?: number | null;
  type_code?: ElectronicTaxTypeCode | '';
  state?: ElectronicTaxState | '';
  folio?: number | null;
  receiver_rut?: string;
  issue_date_from?: string;
  issue_date_to?: string;
  page?: number;
  page_size?: number;
}

export interface ElectronicTaxMutationResponse {
  document: ElectronicTaxDocument;
  idempotent_replay: boolean;
}

export interface ElectronicTaxDetailResponse {
  document: ElectronicTaxDocument;
}

export interface FolioAuthorizationSummary {
  type_code: ElectronicTaxTypeCode;
  status: string;
  start_folio: number;
  end_folio: number;
  next_folio: number;
  available: number;
}

export interface FolioSummaryResponse {
  authorizations: FolioAuthorizationSummary[];
}

export interface ElectronicTaxNoteRequest {
  version: number;
  reason: ElectronicTaxReferenceReason;
  description: string;
  correction?: Record<string, string>;
}
