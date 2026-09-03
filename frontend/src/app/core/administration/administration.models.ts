export type MembershipStatus = 'INVITED' | 'ACTIVE' | 'SUSPENDED' | 'LEFT';
export type RoleStatus = 'ACTIVE' | 'INACTIVE';
export type PermissionScope = 'COMPANY_ONLY' | 'TENANT_GLOBAL' | 'BRANCH_SCOPED';
export type PaymentKind = 'CASH' | 'TRANSFER' | 'ONLINE' | 'OTHER';

export interface AdminCompany {
  id: number;
  name: string;
  rut: string;
  legal_name: string;
  business_activity: string;
  contact_email: string;
  phone: string;
  address: string;
  commune: string;
  city: string;
  is_active: boolean;
}

export interface AdminBranch {
  id: number;
  company: number;
  code: string;
  name: string;
  address: string;
  commune: string;
  city: string;
  phone: string;
  is_active: boolean;
}

export interface AdminPermission {
  id: number;
  code: string;
  scope_behavior: PermissionScope;
}

export interface AdminRole {
  id: number;
  name: string;
  status: RoleStatus;
  permission_codes: string[];
}

export interface AdminUser {
  id: number;
  user_id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  status: MembershipStatus;
  branch_ids: number[];
  role_ids: number[];
  role_names: string[];
}

export interface AdminPaymentMethod {
  id: number;
  code: string;
  name: string;
  kind: PaymentKind;
  is_active: boolean;
  sort_order: number;
}

export interface AdminOrderStatus {
  id: number;
  code: string;
  display_name: string;
  sort_order: number;
  is_active: boolean;
  is_system: boolean;
}

export interface AdminCompanySettings {
  vat_rate: string;
  currency: string;
  timezone: string;
  payment_provider: string;
  payment_sandbox_enabled: boolean;
  notification_sender_email: string;
  updated_at: string;
}

export interface AdminEvent {
  id: number;
  event_type: string;
  resource_type: string;
  resource_id: string;
  actor_name: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AdministrationOverview {
  company: AdminCompany;
  branches: AdminBranch[];
  users: AdminUser[];
  roles: AdminRole[];
  permissions: AdminPermission[];
  payment_methods: AdminPaymentMethod[];
  order_statuses: AdminOrderStatus[];
  settings: AdminCompanySettings;
  events: AdminEvent[];
}
