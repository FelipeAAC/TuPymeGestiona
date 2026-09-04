import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { PortalService } from '../../core/portal/portal.service';

@Component({
  selector: 'app-portal-register',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './portal-register.html',
  styleUrl: './portal-register.scss',
})
export class PortalRegister {
  private readonly portalService = inject(PortalService);
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly router = inject(Router);

  readonly isSubmitting = signal(false);
  readonly errorMessage = signal('');

  readonly form = this.formBuilder.group({
    firstName: ['', [Validators.required, Validators.maxLength(150)]],
    lastName: ['', [Validators.maxLength(150)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

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
        email: value.email.trim(),
        password: value.password,
        first_name: value.firstName.trim(),
        last_name: value.lastName.trim(),
      })
      .pipe(finalize(() => this.isSubmitting.set(false)))
      .subscribe({
        next: () => void this.router.navigate(['/portal']),
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
