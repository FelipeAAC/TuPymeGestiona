import { Component, input, output } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { OrganizationBranch } from '../../../core/organization/organization.models';
import { Warehouse } from '../../../core/warehouses/warehouses.models';

export type WarehouseEditorForm = FormGroup<{
  code: FormControl<string>;
  name: FormControl<string>;
  branchId: FormControl<number | null>;
}>;

@Component({
  selector: 'app-warehouse-editor',
  imports: [ReactiveFormsModule],
  templateUrl: './warehouse-editor.html',
  styleUrl: './warehouse-editor.scss',
})
export class WarehouseEditor {
  readonly editingWarehouse = input<Warehouse | null>(null);
  readonly branches = input<OrganizationBranch[]>([]);
  readonly warehouseForm = input.required<WarehouseEditorForm>();
  readonly isSaving = input(false);
  readonly saveErrorMessage = input('');

  readonly closed = output<void>();
  readonly submitted = output<void>();

  hasBranch(branchId: number): boolean {
    return this.branches().some((branch) => branch.id === branchId);
  }

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
