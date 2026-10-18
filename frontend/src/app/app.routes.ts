import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';
import { permissionGuard } from './core/auth/permission.guard';
import { portalAuthGuard } from './core/portal/portal-auth.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full',
  },
  {
    path: 'portal',
    loadComponent: () => import('./pages/portal/portal').then((module) => module.Portal),
  },
  {
    path: 'portal/register',
    loadComponent: () =>
      import('./pages/portal-register/portal-register').then((module) => module.PortalRegister),
  },
  {
    path: 'portal/seller-onboarding',
    canActivate: [portalAuthGuard],
    loadComponent: () =>
      import('./pages/portal-seller-onboarding/portal-seller-onboarding').then(
        (module) => module.PortalSellerOnboarding,
      ),
  },
  {
    path: 'portal/account',
    canActivate: [portalAuthGuard],
    loadComponent: () =>
      import('./pages/portal-account/portal-account').then((module) => module.PortalAccountPage),
  },
  {
    path: 'portal/payment-result',
    canActivate: [portalAuthGuard],
    loadComponent: () =>
      import('./pages/payment-result/payment-result').then((module) => module.PaymentResult),
  },
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login').then((module) => module.Login),
  },
  {
    path: 'app',
    loadComponent: () => import('./layouts/app-shell/app-shell').then((module) => module.AppShell),
    canActivate: [authGuard],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full',
      },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./pages/dashboard/dashboard').then((module) => module.Dashboard),
      },
      {
        path: 'products',
        canActivate: [permissionGuard('catalog.products.view')],
        loadComponent: () => import('./pages/products/products').then((module) => module.Products),
      },
      {
        path: 'categories',
        canActivate: [permissionGuard('catalog.categories.manage')],
        loadComponent: () =>
          import('./pages/categories/categories').then((module) => module.Categories),
      },
      {
        path: 'brands',
        canActivate: [permissionGuard('catalog.brands.manage')],
        loadComponent: () => import('./pages/brands/brands').then((module) => module.Brands),
      },
      {
        path: 'suppliers',
        canActivate: [permissionGuard('catalog.suppliers.manage')],
        loadComponent: () =>
          import('./pages/suppliers/suppliers').then((module) => module.Suppliers),
      },
      {
        path: 'warehouses',
        canActivate: [permissionGuard('organizations.warehouses.manage')],
        loadComponent: () =>
          import('./pages/warehouses/warehouses').then((module) => module.Warehouses),
      },
      {
        path: 'customers',
        canActivate: [permissionGuard('customers.manage')],
        loadComponent: () =>
          import('./pages/customers/customers').then((module) => module.Customers),
      },
      {
        path: 'inventory',
        canActivate: [
          permissionGuard(
            'inventory.stocks.manage',
            'inventory.movements.manage',
            'inventory.transfers.manage',
          ),
        ],
        loadComponent: () =>
          import('./pages/inventory/inventory').then((module) => module.Inventory),
      },
      {
        path: 'orders',
        canActivate: [permissionGuard('orders.manage')],
        loadComponent: () => import('./pages/orders/orders').then((module) => module.Orders),
      },
      {
        path: 'sales',
        canActivate: [permissionGuard('sales.manage')],
        loadComponent: () => import('./pages/sales/sales').then((module) => module.Sales),
      },
      {
        path: 'electronic-tax',
        canActivate: [
          permissionGuard('electronic_tax_document.view', 'electronic_tax_folio.manage'),
        ],
        loadComponent: () =>
          import('./pages/electronic-tax/electronic-tax').then((module) => module.ElectronicTax),
      },
      {
        path: 'administration',
        canActivate: [permissionGuard('administration.manage')],
        loadComponent: () =>
          import('./pages/administration/administration').then((module) => module.Administration),
      },
      {
        path: 'reports',
        canActivate: [permissionGuard('administration.manage', 'inventory.stocks.manage')],
        loadComponent: () => import('./pages/reports/reports').then((module) => module.Reports),
      },
    ],
  },
  {
    path: '**',
    redirectTo: 'login',
  },
];
