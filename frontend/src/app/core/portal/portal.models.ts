export interface PortalBranch {
  id: number;
  code: string;
  name: string;
  address: string;
  commune: string;
  city: string;
}

export interface PortalStore {
  id: number;
  name: string;
  legal_name: string;
  business_activity: string;
  commune: string;
  city: string;
  branches: PortalBranch[];
}

export interface PortalCategory {
  id: number;
  name: string;
}

export interface PortalVariant {
  id: number;
  sku: string;
  gtin: string;
  base_price: string;
  available_quantity: string;
  available: boolean;
}

export interface PortalProduct {
  id: number;
  name: string;
  description: string;
  image_url: string;
  category: PortalCategory;
  brand: { id: number; name: string } | null;
  variants: PortalVariant[];
  available: boolean;
}

export interface PortalCatalogResponse {
  store: { id: number; name: string; business_activity: string };
  categories: PortalCategory[];
  products: PortalProduct[];
}

export interface PortalAccount {
  company: number;
  company_name: string;
  customer: number;
  customer_name: string;
  email: string;
  phone: string;
  address: string;
  commune: string;
  city: string;
}

export interface PortalOrderItem {
  id: number;
  variant: number;
  variant_sku: string;
  product_name: string;
  quantity: string;
  unit_price: string;
  line_total: string;
}

export interface PortalOrder {
  id: number;
  company: number;
  branch: number;
  warehouse: number;
  customer: number;
  number: number;
  status: 'DRAFT' | 'CONFIRMED' | 'PREPARED' | 'DELIVERED' | 'CANCELLED';
  notes: string;
  delivery_address: string;
  delivery_commune: string;
  delivery_city: string;
  created_at: string;
  updated_at: string;
  items: PortalOrderItem[];
  total: string;
}

export interface PortalRegistrationInput {
  company: number;
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone: string;
  address: string;
  commune: string;
  city: string;
}

export interface PortalOrderInput {
  company: number;
  branch: number;
  delivery_address: string;
  delivery_commune: string;
  delivery_city: string;
  notes: string;
  items: { variant: number; quantity: string }[];
}

export type MercadoPagoStatus =
  | 'CREATING'
  | 'READY'
  | 'PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'REFUNDED'
  | 'UNCERTAIN';

export interface PortalMercadoPagoPayment {
  id: number;
  order: number;
  status: MercadoPagoStatus;
  amount: string;
  currency: string;
  preference_id: string;
  checkout_url: string;
  provider_status: string;
  provider_status_detail: string;
  last_payment_id: string;
  updated_at: string;
  sale: number | null;
}
