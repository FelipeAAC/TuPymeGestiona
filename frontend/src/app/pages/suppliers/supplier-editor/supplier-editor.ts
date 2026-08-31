import { Component, input, output } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { Supplier, SupplierStatus } from '../../../core/suppliers/suppliers.models';

export type SupplierEditorForm = FormGroup<{
  name: FormControl<string>;
  contactName: FormControl<string>;
  email: FormControl<string>;
  phone: FormControl<string>;
  status: FormControl<SupplierStatus>;
}>;

@Component({
  selector: 'app-supplier-editor',
  imports: [ReactiveFormsModule],
  templateUrl: './supplier-editor.html',
  styleUrl: './supplier-editor.scss',
})
export class SupplierEditor {
  readonly editingSupplier = input<Supplier | null>(null);
  readonly supplierForm = input.required<SupplierEditorForm>();
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
