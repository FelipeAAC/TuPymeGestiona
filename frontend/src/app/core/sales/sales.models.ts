export type SaleStatus = 'PENDING' | 'PARTIAL' | 'PAID' | 'CANCELLED';

export type SaleEventType = 'CREATED' | 'PAYMENT_RECORDED' | 'CANCELLED';

export interface SalePayment {
  id: number;
  amount: string;
  reference: string;
  idempotency_key: string;
  recorded_by: number;
  created_at: string;
}

export interface SaleEvent {
  id: number;
  event_type: SaleEventType;
  previous_status: SaleStatus | '';
  new_status: SaleStatus;
  payment: number | null;
  amount: string | null;
  reference: string;
  performed_by: number;
  created_at: string;
}

export interface Sale {
  id: number;
  company: number;
  branch: number;
  order: number;
  order_number: number;
  customer: number;
  customer_code: string;
  customer_name: string;
  number: number;
  status: SaleStatus;
  total_amount: string;
  paid_amount: string;
  balance: string;
  idempotency_key: string;
  created_by: number;
  cancelled_by: number | null;
  created_at: string;
  updated_at: string;
  cancelled_at: string | null;
  payments: SalePayment[];
  events: SaleEvent[];
}

export interface SalePagination {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next_page: number | null;
  previous_page: number | null;
}

export interface SaleListResponse {
  sales: Sale[];
  pagination: SalePagination;
}

export interface SaleListQuery {
  status?: SaleStatus | '';
  branch?: number | null;
  customer?: number | null;
  search?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
}

export interface SaleOptionBranch {
  id: number;
  code: string;
  name: string;
}

export interface SaleOptionDeliveredOrder {
  id: number;
  number: number;
  branch: number;
  customer: number;
  customer_code: string;
  customer_name: string;
  total: string;
}

export interface SaleOptionsResponse {
  permissions: {
    manage: boolean;
  };
  branches: SaleOptionBranch[];
  delivered_orders: SaleOptionDeliveredOrder[];
}

export interface SaleResponse {
  sale: Sale;
}

export interface SaleCreateResponse extends SaleResponse {
  idempotent_replay: boolean;
}

export interface SalePaymentResponse extends SaleResponse {
  payment: SalePayment;
  idempotent_replay: boolean;
}

export interface SaleCancelResponse extends SaleResponse {
  already_cancelled: boolean;
}
