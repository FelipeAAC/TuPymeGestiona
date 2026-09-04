export type MembershipStatus = 'INVITED' | 'ACTIVE' | 'SUSPENDED' | 'LEFT';
export type RoleStatus = 'ACTIVE' | 'INACTIVE';
export type PaymentKind = 'CASH' | 'TRANSFER' | 'ONLINE' | 'OTHER';
export type CategoryStatus = 'ACTIVE' | 'INACTIVE';
export type ProductStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE';

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

export interface OrganizationMembership {
  id: number;
  status: MembershipStatus;
  company: { id: number; name: string };
  branches: Array<{ id: number; code: string; name: string }>;
  permissions?: string[];
}

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
  scope_behavior: 'COMPANY_ONLY' | 'TENANT_GLOBAL' | 'BRANCH_SCOPED';
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

export interface AdministrationOverview {
  company: AdminCompany;
  branches: AdminBranch[];
  users: AdminUser[];
  roles: AdminRole[];
  permissions: AdminPermission[];
  payment_methods: AdminPaymentMethod[];
  order_statuses: AdminOrderStatus[];
  settings: AdminCompanySettings;
  events: Array<{
    id: number;
    event_type: string;
    resource_type: string;
    resource_id: string;
    actor_name: string;
    metadata: Record<string, unknown>;
    created_at: string;
  }>;
}

export interface Category {
  id: number;
  name: string;
  parent: { id: number; name: string } | null;
  status: CategoryStatus;
}

export interface Brand {
  id: number;
  name: string;
}

export interface Product {
  id: number;
  name: string;
  description: string;
  image_url: string;
  status: ProductStatus;
  category: { id: number; name: string };
  brand: Brand | null;
  variants: Array<{
    id: number;
    sku: string;
    gtin: string;
    base_price: string;
    status: ProductStatus;
  }>;
}

export interface Supplier {
  id: number;
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  status: 'ACTIVE' | 'INACTIVE';
}

export interface Warehouse {
  id: number;
  company: number;
  branch: number | null;
  code: string;
  name: string;
}

export interface CatalogState {
  categories: Category[];
  products: Product[];
  brands: Brand[];
}

export interface DirectoryState {
  suppliers: Supplier[];
  warehouses: Warehouse[];
}
