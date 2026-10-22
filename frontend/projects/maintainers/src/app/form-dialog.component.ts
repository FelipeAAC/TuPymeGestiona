import { CommonModule } from '@angular/common';
import { Component, EventEmitter, HostListener, Input, Output, SimpleChanges } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

export type FormDialogFieldType = 'text' | 'email' | 'number' | 'textarea' | 'select' | 'checkbox' | 'multi-select';

export interface FormDialogOption {
  value: string | number;
  label: string;
}

export interface FormDialogField {
  key: string;
  label: string;
  type: FormDialogFieldType;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  rows?: number;
  min?: number;
  options?: FormDialogOption[];
}

@Component({
  selector: 'maintainers-form-dialog',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './form-dialog.component.html',
  styleUrl: './form-dialog.component.scss',
})
export class FormDialogComponent {
  @Input() title = 'Editar registro';
  @Input() fields: FormDialogField[] = [];
  @Input() initialValue: Record<string, unknown> = {};
  @Input() submitLabel = 'Guardar';
  @Input() busy = false;
  @Output() saved = new EventEmitter<Record<string, unknown>>();
  @Output() canceled = new EventEmitter<void>();

  form = new FormGroup<Record<string, FormControl<unknown>>>({});

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['fields'] || changes['initialValue']) this.rebuildForm();
  }

  private rebuildForm(): void {
    const controls: Record<string, FormControl<unknown>> = {};
    for (const field of this.fields) {
      const initial = this.initialValue[field.key] ?? (field.type === 'checkbox' ? false : field.type === 'multi-select' ? [] : '');
      const validators = field.required ? [Validators.required] : [];
      if (field.type === 'email') validators.push(Validators.email);
      if (field.type === 'number' && field.min !== undefined) validators.push(Validators.min(field.min));
      controls[field.key] = new FormControl(initial, { nonNullable: true, validators });
    }
    this.form = new FormGroup(controls);
  }

  control(field: FormDialogField): FormControl<unknown> {
    return this.form.controls[field.key];
  }

  submit(): void {
    if (this.busy) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    this.saved.emit(this.form.getRawValue());
  }

  cancel(): void {
    if (!this.busy) this.canceled.emit();
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.cancel();
  }
}
