export type CatalogProductStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE';

export interface CatalogCategory {
  id: number;
  name: string;
}

export interface CatalogBrand {
  id: number;
  name: string;
}

export interface CatalogProductVariant {
  id: number;
  sku: string;
  gtin: string;
  base_price: string;
  status: CatalogProductStatus;
}

export interface CatalogProduct {
  id: number;
  name: string;
  status: CatalogProductStatus;
  category: CatalogCategory;
  brand: CatalogBrand | null;
  variants: CatalogProductVariant[];
}

export interface CatalogProductListResponse {
  products: CatalogProduct[];
}
