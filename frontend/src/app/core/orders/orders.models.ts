export type OrderStatus = 'DRAFT' | 'CONFIRMED' | 'PREPARED' | 'DELIVERED' | 'CANCELLED';

export type OrderMovementKind = 'CONFIRMATION' | 'CANCELLATION';

export interface OrderStockMovement {
  id: number;
  kind: OrderMovementKind;
  inventory_movement: number;
  movement_type: string;
  quantity_delta: string;
  created_by: number;
  created_at: string;
}

export interface OrderItem {
  id: number;
  variant: number;
  variant_sku: string;
  product_name: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  stock_movements: OrderStockMovement[];
}

export interface Order {
  id: number;
  company: number;
  branch: number;
  warehouse: number;
  customer: number;
  number: number;
  status: OrderStatus;
  notes: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  total: string;
}

export interface OrderPagination {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next_page: number | null;
  previous_page: number | null;
}

export interface OrderListResponse {
  orders: Order[];
  pagination: OrderPagination;
}

export interface OrderResponse {
  order: Order;
}

export interface OrderListQuery {
  status?: OrderStatus | '';
  branch?: number | null;
  customer?: number | null;
  search?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
}

export interface OrderItemInput {
  variant: number;
  quantity: number;
  unit_price: number;
}

export interface OrderInput {
  branch: number;
  warehouse: number;
  customer: number;
  notes: string;
  items: OrderItemInput[];
}

export interface OrderOptionBranch {
  id: number;
  code: string;
  name: string;
}

export interface OrderOptionWarehouse {
  id: number;
  branch: number | null;
  code: string;
  name: string;
}

export interface OrderOptionCustomer {
  id: number;
  code: string;
  name: string;
}

export interface OrderOptionVariant {
  id: number;
  product: number;
  product_name: string;
  sku: string;
  base_price: string;
}

export interface OrderOptionsResponse {
  permissions: {
    manage: boolean;
  };
  branches: OrderOptionBranch[];
  warehouses: OrderOptionWarehouse[];
  customers: OrderOptionCustomer[];
  variants: OrderOptionVariant[];
}
