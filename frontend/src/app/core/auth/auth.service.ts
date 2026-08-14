import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable, switchMap } from 'rxjs';

import { AuthUser, LoginCredentials, LoginResponse } from './auth.models';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);

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
    );
  }

  me(): Observable<AuthUser> {
    return this.http.get<LoginResponse>('/api/auth/me/').pipe(map((response) => response.user));
  }

  logout(): Observable<void> {
    return this.http.post<void>('/api/auth/logout/', {});
  }
}
