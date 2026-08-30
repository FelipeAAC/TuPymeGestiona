import { Routes } from '@angular/router';

import { Brands } from './pages/brands/brands';
import { authGuard } from './core/auth/auth.guard';
import { AppShell } from './layouts/app-shell/app-shell';
import { Categories } from './pages/categories/categories';
import { Customers } from './pages/customers/customers';
import { Dashboard } from './pages/dashboard/dashboard';
import { Login } from './pages/login/login';
import { Products } from './pages/products/products';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full',
  },
  {
    path: 'login',
    component: Login,
  },
  {
    path: 'app',
    component: AppShell,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full',
      },
      {
        path: 'dashboard',
        component: Dashboard,
      },
      {
        path: 'products',
        component: Products,
      },
      {
        path: 'categories',
        component: Categories,
      },
      {
        path: 'brands',
        component: Brands,
      },
      {
        path: 'customers',
        component: Customers,
      },
    ],
  },
  {
    path: '**',
    redirectTo: 'login',
  },
];
