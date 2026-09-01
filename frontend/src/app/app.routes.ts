import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full',
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
    ],
  },
  {
    path: '**',
    redirectTo: 'login',
  },
];
