export type CustomerStatus = 'ACTIVE' | 'INACTIVE';

export type CustomerOrdering =
  'name' | '-name' | 'code' | '-code' | 'created_at' | '-created_at' | 'updated_at' | '-updated_at';

export interface Customer {
  id: number;
  company: number;
  code: string;
  name: string;
  tax_id: string;
  email: string;
  phone: string;
  status: CustomerStatus;
  created_at: string;
  updated_at: string;
}

export interface CustomerPagination {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next_page: number | null;
  previous_page: number | null;
}

export interface CustomerListResponse {
  customers: Customer[];
  pagination: CustomerPagination;
}

export interface CustomerListQuery {
  search?: string;
  status?: CustomerStatus;
  ordering: CustomerOrdering;
  page: number;
  page_size: number;
}

export interface CustomerInput {
  code: string;
  name: string;
  tax_id: string;
  email: string;
  phone: string;
  status: CustomerStatus;
}

export interface CustomerResponse {
  customer: Customer;
}
