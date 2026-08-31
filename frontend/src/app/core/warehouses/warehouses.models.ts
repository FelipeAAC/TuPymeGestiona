export interface Warehouse {
  id: number;
  company: number;
  branch: number | null;
  code: string;
  name: string;
}

export interface WarehouseListResponse {
  warehouses: Warehouse[];
}

export interface WarehouseInput {
  branch: number | null;
  code: string;
  name: string;
}

export interface WarehouseResponse {
  warehouse: Warehouse;
}
