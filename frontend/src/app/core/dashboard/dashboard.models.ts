export type DashboardAlertSeverity = 'info' | 'warning' | 'danger';
export type DashboardModuleStatus = 'OPERATIVE' | 'RESTRICTED';
export type DashboardActivityKind = 'sale' | 'inventory' | 'order';

export interface DashboardAlert {
  code: string;
  severity: DashboardAlertSeverity;
  title: string;
  detail: string;
  count: number;
  route: string;
}

export interface DashboardActivity {
  kind: DashboardActivityKind;
  title: string;
  detail: string;
  occurred_at: string;
  route: string;
}

export interface DashboardModule {
  code: string;
  label: string;
  available: boolean;
  status: DashboardModuleStatus;
  route: string;
}

export interface DashboardOverviewResponse {
  company: {
    id: number;
    name: string;
  };
  generated_at: string;
  permissions: {
    sales: boolean;
    orders: boolean;
    inventory: boolean;
    customers: boolean;
    reports: boolean;
    administration: boolean;
  };
  metrics: {
    sales_today_amount: string | null;
    sales_today_count: number | null;
    pending_orders: number | null;
    low_stock: number | null;
    critical_stock: number | null;
    out_of_stock: number | null;
    active_customers: number | null;
  };
  alerts: DashboardAlert[];
  activity: DashboardActivity[];
  modules: DashboardModule[];
}
