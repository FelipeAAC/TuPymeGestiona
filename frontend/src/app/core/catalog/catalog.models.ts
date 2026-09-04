export type CatalogProductStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE';
export type CatalogCategoryStatus = 'ACTIVE' | 'INACTIVE';

export interface CatalogCategory {
  id: number;
  name: string;
}

export interface CatalogCategoryDetail {
  id: number;
  name: string;
  parent: CatalogCategory | null;
  status: CatalogCategoryStatus;
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
  description: string;
  image_url: string;
  status: CatalogProductStatus;
  category: CatalogCategory;
  brand: CatalogBrand | null;
  variants: CatalogProductVariant[];
}

export interface CatalogProductListResponse {
  products: CatalogProduct[];
}

export interface CatalogProductOptionsResponse {
  categories: CatalogCategory[];
  brands: CatalogBrand[];
}

export interface CatalogProductVariantCreateInput {
  sku: string;
  gtin: string;
  base_price: string;
}

export interface CatalogProductCreateInput {
  name: string;
  description: string;
  image_url: string;
  category: number;
  brand: number | null;
  variant: CatalogProductVariantCreateInput;
}

export interface CatalogProductUpdateInput {
  name?: string;
  description?: string;
  image_url?: string;
  category?: number;
  brand?: number | null;
  status?: CatalogProductStatus;
}

export interface CatalogProductCreateResponse {
  product: CatalogProduct;
}

export interface CatalogProductUpdateResponse {
  product: CatalogProduct;
}

export interface CatalogCategoryListResponse {
  categories: CatalogCategoryDetail[];
}

export interface CatalogCategoryCreateInput {
  name: string;
  parent: number | null;
}

export interface CatalogCategoryUpdateInput {
  name?: string;
  parent?: number | null;
  status?: CatalogCategoryStatus;
}

export interface CatalogCategoryCreateResponse {
  category: {
    id: number;
    name: string;
    parent: CatalogCategory | null;
  };
}

export interface CatalogCategoryUpdateResponse {
  category: CatalogCategoryDetail;
}

export interface CatalogBrandListResponse {
  brands: CatalogBrand[];
}

export interface CatalogBrandCreateInput {
  name: string;
}

export interface CatalogBrandCreateResponse {
  brand: CatalogBrand;
}
