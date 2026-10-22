import { MaintainerContext } from './models';

/** Small contract fixtures used by manual/API smoke checks for the protected workspace. */
export const platformContextFixture: MaintainerContext = {
  user: { id: 1, username: 'platform', email: 'platform@example.test', first_name: 'Platform', last_name: 'Admin', access_modes: ['PLATFORM_ADMIN'] },
  companies: [{ id: 1, name: 'Empresa demo', legal_name: 'Empresa demo SpA', rut: '', is_active: true, branches_count: 1, users_count: 1, products_count: 2, orders_count: 0 }],
  summary: { total_companies: 1, active_companies: 1, total_branches: 1, total_users: 1, total_products: 2, total_orders: 0, total_categories: 1, total_brands: 0, total_suppliers: 0, total_warehouses: 1 },
};

export const nonPlatformDeniedFixture = { status: 403, error: { detail: 'No tienes permisos para acceder a esta consola.' } };
export const validationErrorFixture = { status: 400, error: { name: ['Este campo es obligatorio.'] } };
