import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';
import { AppHome } from './pages/app-home/app-home';
import { Login } from './pages/login/login';

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
    component: AppHome,
    canActivate: [authGuard],
  },
  {
    path: '**',
    redirectTo: 'login',
  },
];
