import { Component, input, output } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { Customer, CustomerStatus } from '../../../core/customers/customers.models';

export type CustomerEditorForm = FormGroup<{
  code: FormControl<string>;
  name: FormControl<string>;
  taxId: FormControl<string>;
  email: FormControl<string>;
  phone: FormControl<string>;
  status: FormControl<CustomerStatus>;
}>;

@Component({
  selector: 'app-customer-editor',
  imports: [ReactiveFormsModule],
  templateUrl: './customer-editor.html',
  styleUrl: './customer-editor.scss',
})
export class CustomerEditor {
  readonly editingCustomer = input<Customer | null>(null);
  readonly customerForm = input.required<CustomerEditorForm>();
  readonly isSaving = input(false);
  readonly saveErrorMessage = input('');

  readonly closed = output<void>();
  readonly submitted = output<void>();

  closeFromBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.requestClose();
    }
  }

  requestClose(): void {
    if (!this.isSaving()) {
      this.closed.emit();
    }
  }
}
