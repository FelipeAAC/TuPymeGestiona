export type SupplierStatus = 'ACTIVE' | 'INACTIVE';

export interface Supplier {
  id: number;
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  status: SupplierStatus;
}

export interface SupplierListResponse {
  suppliers: Supplier[];
}

export interface SupplierInput {
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  status: SupplierStatus;
}

export interface SupplierResponse {
  supplier: Supplier;
}
