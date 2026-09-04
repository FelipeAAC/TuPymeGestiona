export interface ReportCompanyOption {
  id: number;
  name: string;
}

export interface ReportBranchOption {
  id: number;
  code: string;
  name: string;
}

export interface ReportSellerOption {
  id: number;
  username: string;
  email: string;
}

export interface ReportWarehouseOption {
  id: number;
  code: string;
  name: string;
  branch_id: number | null;
  branch__name: string | null;
}

export interface ReportCategoryOption {
  id: number;
  name: string;
}

export interface ReportOptionsResponse {
  company: ReportCompanyOption;
  permissions: {
    sales: boolean;
    inventory: boolean;
  };
  branches: ReportBranchOption[];
  sellers: ReportSellerOption[];
  warehouses: ReportWarehouseOption[];
  categories: ReportCategoryOption[];
}

export interface SalesReportQuery {
  date_from?: string;
  date_to?: string;
  branch?: number | null;
  seller?: number | null;
}

export interface SalesReportRow {
  id: number;
  number: number;
  date: string;
  branch: string;
  branch_code: string;
  seller: string;
  seller_username: string;
  customer: string;
  customer_code: string;
  status: 'PENDING' | 'PARTIAL' | 'PAID' | 'CANCELLED';
  total_amount: string;
  paid_amount: string;
  balance: string;
}

export interface SalesReportResponse {
  filters: {
    date_from: string;
    date_to: string;
    branch: string;
    seller: string;
  };
  summary: {
    records: number;
    active_sales: number;
    gross_total: string;
    paid_total: string;
    balance_total: string;
  };
  rows: SalesReportRow[];
}

export type StockLevelFilter = 'ALL' | 'OUT' | 'CRITICAL' | 'AVAILABLE';

export interface InventoryReportQuery {
  warehouse?: number | null;
  category?: number | null;
  stock_level?: StockLevelFilter;
  critical_threshold?: number;
}

export interface InventoryReportRow {
  id: number;
  warehouse: string;
  warehouse_code: string;
  branch: string;
  category: string;
  product: string;
  sku: string;
  quantity: string;
  unit_price: string;
  reference_value: string;
  stock_level: 'OUT' | 'CRITICAL' | 'AVAILABLE';
}

export interface InventoryReportResponse {
  filters: {
    warehouse: string;
    category: string;
    stock_level: string;
    critical_threshold: string;
  };
  summary: {
    records: number;
    total_units: string;
    reference_value: string;
    critical_count: number;
    out_count: number;
    critical_threshold: string;
  };
  valuation_note: string;
  rows: InventoryReportRow[];
}
