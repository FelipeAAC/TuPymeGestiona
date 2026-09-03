import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { PortalStore } from '../../core/portal/portal.models';
import { PortalService } from '../../core/portal/portal.service';

@Component({
  selector: 'app-portal-register',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './portal-register.html',
  styleUrl: './portal-register.scss',
})
export class PortalRegister implements OnInit {
  private readonly portalService = inject(PortalService);
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly router = inject(Router);

  readonly stores = signal<PortalStore[]>([]);
  readonly isLoading = signal(false);
  readonly isSubmitting = signal(false);
  readonly errorMessage = signal('');

  readonly form = this.formBuilder.group({
    company: [0, [Validators.required, Validators.min(1)]],
    firstName: ['', [Validators.required, Validators.maxLength(150)]],
    lastName: ['', [Validators.maxLength(150)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    phone: ['', [Validators.maxLength(50)]],
    address: ['', [Validators.required, Validators.maxLength(220)]],
    commune: ['', [Validators.required, Validators.maxLength(120)]],
    city: ['', [Validators.required, Validators.maxLength(120)]],
  });

  ngOnInit(): void {
    this.isLoading.set(true);
    this.portalService
      .listStores()
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: (stores) => {
          this.stores.set(stores);
          this.form.patchValue({ company: stores[0]?.id ?? 0 });
        },
        error: () => this.errorMessage.set('No pudimos cargar las tiendas disponibles.'),
      });
  }

  submit(): void {
    if (this.form.invalid || this.isSubmitting()) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    this.errorMessage.set('');
    this.isSubmitting.set(true);
    this.portalService
      .register({
        company: value.company,
        email: value.email.trim(),
        password: value.password,
        first_name: value.firstName.trim(),
        last_name: value.lastName.trim(),
        phone: value.phone.trim(),
        address: value.address.trim(),
        commune: value.commune.trim(),
        city: value.city.trim(),
      })
      .pipe(finalize(() => this.isSubmitting.set(false)))
      .subscribe({
        next: () => void this.router.navigate(['/portal/account']),
        error: (error: HttpErrorResponse) => {
          this.errorMessage.set(
            error.status === 409
              ? (error.error?.detail ?? 'Ya existe una cuenta con ese correo electrónico.')
              : error.status === 400
                ? 'Revisa los datos. La contraseña debe cumplir los requisitos de seguridad.'
                : 'No pudimos crear la cuenta. Inténtalo nuevamente.',
          );
        },
      });
  }
}
