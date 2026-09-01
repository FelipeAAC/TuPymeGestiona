import { Type } from '@angular/core';
import { Route } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';
import { AppShell } from './layouts/app-shell/app-shell';
import { Brands } from './pages/brands/brands';
import { Categories } from './pages/categories/categories';
import { Customers } from './pages/customers/customers';
import { Dashboard } from './pages/dashboard/dashboard';
import { Inventory } from './pages/inventory/inventory';
import { Login } from './pages/login/login';
import { Orders } from './pages/orders/orders';
import { Products } from './pages/products/products';
import { Suppliers } from './pages/suppliers/suppliers';
import { Warehouses } from './pages/warehouses/warehouses';
import { routes } from './app.routes';

describe('application routes', () => {
  it('preserves the default and fallback redirects', () => {
    expect(routes[0]).toMatchObject({
      path: '',
      redirectTo: 'login',
      pathMatch: 'full',
    });
    expect(routes.at(-1)).toMatchObject({
      path: '**',
      redirectTo: 'login',
    });
  });

  it('lazy-loads login and the protected application shell', async () => {
    const loginRoute = routeByPath(routes, 'login');
    const appRoute = routeByPath(routes, 'app');

    expect(loginRoute.component).toBeUndefined();
    expect(appRoute.component).toBeUndefined();
    expect(appRoute.canActivate).toEqual([authGuard]);

    const [loginComponent, shellComponent] = await Promise.all([
      loadComponent(loginRoute),
      loadComponent(appRoute),
    ]);

    expect(loginComponent).toBe(Login);
    expect(shellComponent).toBe(AppShell);
  });

  it('lazy-loads every feature page from the application shell', async () => {
    const appRoute = routeByPath(routes, 'app');
    const featureRoutes = (appRoute.children ?? []).filter((route) => !route.redirectTo);
    const expectedComponents = new Map<string, Type<unknown>>([
      ['dashboard', Dashboard],
      ['products', Products],
      ['categories', Categories],
      ['brands', Brands],
      ['suppliers', Suppliers],
      ['warehouses', Warehouses],
      ['customers', Customers],
      ['inventory', Inventory],
      ['orders', Orders],
    ]);

    expect(featureRoutes.map((route) => route.path)).toEqual([...expectedComponents.keys()]);
    expect(featureRoutes.every((route) => route.component === undefined)).toBe(true);

    const components = await Promise.all(featureRoutes.map((route) => loadComponent(route)));

    expect(components).toEqual([...expectedComponents.values()]);
  });
});

function routeByPath(routeList: Route[], path: string): Route {
  const route = routeList.find((candidate) => candidate.path === path);

  if (!route) {
    throw new Error(`Route not found: ${path}`);
  }

  return route;
}

async function loadComponent(route: Route): Promise<Type<unknown>> {
  if (!route.loadComponent) {
    throw new Error(`Route is not lazy: ${route.path}`);
  }

  return (await route.loadComponent()) as Type<unknown>;
}
