export type SaleStatus = 'PENDING' | 'PARTIAL' | 'PAID' | 'CANCELLED';

export type SaleOrigin = 'ORDER' | 'POS';

export type PaymentMethodKind = 'CASH' | 'TRANSFER' | 'ONLINE' | 'OTHER';

export type SaleEventType = 'CREATED' | 'PAYMENT_RECORDED' | 'CANCELLED';

export interface SalePayment {
  id: number;
  amount: string;
  reference: string;
  idempotency_key: string;
  payment_method?: number | null;
  recorded_by: number;
  created_at: string;
}

export interface SaleItem {
  id: number;
  variant: number;
  sku_snapshot: string;
  product_name_snapshot: string;
  quantity: string;
  unit_price: string;
  line_total: string;
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
  warehouse?: number | null;
  origin?: SaleOrigin;
  order: number | null;
  order_number: number | null;
  customer: number | null;
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
  items?: SaleItem[];
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

export interface SaleOptionWarehouse {
  id: number;
  code: string;
  name: string;
  branch: number | null;
}

export interface SaleOptionPaymentMethod {
  id: number;
  code: string;
  name: string;
  kind: PaymentMethodKind;
}

export interface SaleOptionCustomer {
  id: number;
  code: string;
  name: string;
}

export interface SaleOptionVariant {
  id: number;
  sku: string;
  name: string;
  unit_price: string;
  stock: string;
}

export interface SaleOptionsResponse {
  permissions: {
    manage: boolean;
  };
  branches: SaleOptionBranch[];
  delivered_orders: SaleOptionDeliveredOrder[];
  warehouses?: SaleOptionWarehouse[];
  payment_methods?: SaleOptionPaymentMethod[];
  customers?: SaleOptionCustomer[];
  variants?: SaleOptionVariant[];
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

export interface PosSaleOptionsQuery {
  branch?: number | null;
  warehouse?: number | null;
  search?: string;
}

export interface PosSaleItemCreateRequest {
  variant: number;
  quantity: number | string;
  unit_price?: number | string;
}

export interface PosSaleCreateRequest {
  branch: number;
  warehouse: number;
  customer?: number | null;
  items: PosSaleItemCreateRequest[];
  payment_method: number;
  reference: string;
  idempotency_key: string;
}

export interface PosSaleCreateResponse extends SaleResponse {
  payment: SalePayment;
  idempotent_replay: boolean;
}

export interface SaleReversal {
  id: number;
  amount: string;
  reference: string;
  performed_by: number;
  created_at: string;
}

export interface SaleReverseResponse extends SaleResponse {
  reversal: SaleReversal;
  already_reversed: boolean;
}
