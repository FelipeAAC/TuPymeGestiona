import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable, switchMap, tap } from 'rxjs';

import {
  AccessMode,
  AuthUser,
  LoginCredentials,
  LoginResponse,
  PasswordResetResponse,
} from './auth.models';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);

  private readonly currentUserState = signal<AuthUser | null>(null);
  readonly currentUser = this.currentUserState.asReadonly();

  login(credentials: LoginCredentials): Observable<AuthUser> {
    return this.http.get<{ detail: string }>('/api/auth/csrf/').pipe(
      switchMap(() =>
        this.http.post<LoginResponse>('/api/auth/login/', {
          identifier: credentials.identifier,
          password: credentials.password,
          remember_me: credentials.rememberMe,
        }),
      ),
      map((response) => response.user),
      tap((user) => this.currentUserState.set(user)),
    );
  }

  me(): Observable<AuthUser> {
    return this.http.get<LoginResponse>('/api/auth/me/').pipe(
      map((response) => response.user),
      tap({
        next: (user) => this.currentUserState.set(user),
        error: () => this.currentUserState.set(null),
      }),
    );
  }

  logout(): Observable<void> {
    return this.http
      .post<void>('/api/auth/logout/', {})
      .pipe(tap(() => this.currentUserState.set(null)));
  }

  requestPasswordReset(email: string): Observable<PasswordResetResponse> {
    return this.http.get<{ detail: string }>('/api/auth/csrf/').pipe(
      switchMap(() =>
        this.http.post<PasswordResetResponse>('/api/auth/password-reset/request/', {
          email: email.trim(),
        }),
      ),
    );
  }

  confirmPasswordReset(uid: string, token: string, password: string): Observable<void> {
    return this.http.get<{ detail: string }>('/api/auth/csrf/').pipe(
      switchMap(() =>
        this.http.post<void>('/api/auth/password-reset/confirm/', { uid, token, password }),
      ),
    );
  }

  hasAccessMode(mode: AccessMode): boolean {
    return this.currentUser()?.access_modes.includes(mode) ?? false;
  }

  destinationForUser(user: AuthUser): '/portal' | '/app' | '/access-chooser' {
    const hasCustomer = user.access_modes.includes('CUSTOMER');
    const hasCompanyAdmin = user.access_modes.includes('COMPANY_ADMIN');
    const hasPlatformAdmin = user.access_modes.includes('PLATFORM_ADMIN');
    if ((hasCustomer && hasCompanyAdmin) || (hasPlatformAdmin && user.access_modes.length > 1)) {
      return '/access-chooser';
    }
    if (user.default_app === 'app' || hasCompanyAdmin) return '/app';
    if (hasPlatformAdmin) return '/access-chooser';
    return '/portal';
  }
}
