import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';
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
    path: 'portal/account',
    canActivate: [portalAuthGuard],
    loadComponent: () =>
      import('./pages/portal-account/portal-account').then((module) => module.PortalAccountPage),
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
        loadComponent: () => import('./pages/products/products').then((module) => module.Products),
      },
      {
        path: 'categories',
        loadComponent: () =>
          import('./pages/categories/categories').then((module) => module.Categories),
      },
      {
        path: 'brands',
        loadComponent: () => import('./pages/brands/brands').then((module) => module.Brands),
      },
      {
        path: 'suppliers',
        loadComponent: () =>
          import('./pages/suppliers/suppliers').then((module) => module.Suppliers),
      },
      {
        path: 'warehouses',
        loadComponent: () =>
          import('./pages/warehouses/warehouses').then((module) => module.Warehouses),
      },
      {
        path: 'customers',
        loadComponent: () =>
          import('./pages/customers/customers').then((module) => module.Customers),
      },
      {
        path: 'inventory',
        loadComponent: () =>
          import('./pages/inventory/inventory').then((module) => module.Inventory),
      },
      {
        path: 'orders',
        loadComponent: () => import('./pages/orders/orders').then((module) => module.Orders),
      },
      {
        path: 'sales',
        loadComponent: () => import('./pages/sales/sales').then((module) => module.Sales),
      },
      {
        path: 'electronic-tax',
        loadComponent: () =>
          import('./pages/electronic-tax/electronic-tax').then((module) => module.ElectronicTax),
      },
      {
        path: 'administration',
        loadComponent: () =>
          import('./pages/administration/administration').then((module) => module.Administration),
      },
    ],
  },
  {
    path: '**',
    redirectTo: 'login',
  },
];
