import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { PortalRegister } from './portal-register';

describe('PortalRegister user-first onboarding', () => {
  let http: HttpTestingController;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PortalRegister],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => http.verify());

  it('creates a person without forcing a store or delivery address', () => {
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(PortalRegister);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('select')).toBeNull();

    fixture.componentInstance.form.setValue({
      firstName: 'Ana',
      lastName: 'Pérez',
      email: 'ana@example.com',
      password: 'Clave-segura-2026!',
    });
    fixture.componentInstance.submit();

    http.expectOne('/api/auth/csrf/').flush({ detail: 'ok' });
    const request = http.expectOne('/api/portal/register/');
    expect(request.request.body).toEqual({
      email: 'ana@example.com',
      password: 'Clave-segura-2026!',
      first_name: 'Ana',
      last_name: 'Pérez',
    });
    request.flush({
      user: {
        id: 1,
        username: 'ana@example.com',
        email: 'ana@example.com',
        first_name: 'Ana',
        last_name: 'Pérez',
      },
      account: null,
    });

    expect(navigate).toHaveBeenCalledWith(['/portal']);
  });
});
