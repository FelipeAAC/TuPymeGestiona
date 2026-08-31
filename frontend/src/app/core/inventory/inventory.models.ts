export type InventoryMovementType = 'ENTRY' | 'EXIT' | 'ADJUSTMENT';

export type InventoryTransferStatus = 'COMPLETED' | 'CANCELLED';

export interface InventoryPermissions {
  stocks_manage: boolean;
  movements_manage: boolean;
  transfers_manage: boolean;
}

export interface InventoryWarehouseCapabilities {
  stocks: boolean;
  movements: boolean;
  transfers: boolean;
}

export interface InventoryWarehouseOption {
  id: number;
  branch: number | null;
  branch_name: string;
  code: string;
  name: string;
  capabilities: InventoryWarehouseCapabilities;
}

export interface InventoryVariantOption {
  id: number;
  product: number;
  product_name: string;
  sku: string;
  gtin: string;
  status: string;
}

export interface InventoryOptionsResponse {
  permissions: InventoryPermissions;
  warehouses: InventoryWarehouseOption[];
  variants: InventoryVariantOption[];
}

export interface InventoryStock {
  id: number;
  warehouse: number;
  variant: number;
  quantity: string;
  created_at: string;
  updated_at: string;
}

export interface InventoryStockListResponse {
  stocks: InventoryStock[];
}

export interface InventoryMovement {
  id: number;
  warehouse: number;
  variant: number;
  movement_type: InventoryMovementType;
  quantity_delta: string;
  created_by: number;
  created_at: string;
}

export interface InventoryMovementQuery {
  warehouse?: number;
  variant?: number;
  movement_type?: InventoryMovementType;
}

export interface InventoryMovementInput {
  warehouse: number;
  variant: number;
  movement_type: InventoryMovementType;
  quantity_delta: string;
}

export interface InventoryMovementListResponse {
  movements: InventoryMovement[];
}

export interface InventoryMovementCreateResponse {
  movement: InventoryMovement;
  stock: InventoryStock;
}

export interface InventoryTransferItem {
  variant: number;
  quantity: string;
}

export interface InventoryTransfer {
  id: number;
  source_warehouse: number;
  destination_warehouse: number;
  created_by: number;
  status: InventoryTransferStatus;
  created_at: string;
  items: InventoryTransferItem[];
}

export interface InventoryTransferInput {
  source_warehouse: number;
  destination_warehouse: number;
  items: InventoryTransferItem[];
}

export interface InventoryTransferListResponse {
  transfers: InventoryTransfer[];
}

export interface InventoryTransferCreateResponse {
  transfer: InventoryTransfer;
}
