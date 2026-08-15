import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable, switchMap, tap } from 'rxjs';

import { AuthUser, LoginCredentials, LoginResponse } from './auth.models';

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
}
