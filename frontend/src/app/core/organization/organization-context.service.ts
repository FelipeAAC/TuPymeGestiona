import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable, tap } from 'rxjs';

import { OrganizationContextResponse, OrganizationMembership } from './organization.models';

@Injectable({
  providedIn: 'root',
})
export class OrganizationContextService {
  private readonly http = inject(HttpClient);

  private readonly membershipsState = signal<OrganizationMembership[]>([]);
  readonly memberships = this.membershipsState.asReadonly();

  private readonly selectedMembershipState = signal<OrganizationMembership | null>(null);
  readonly selectedMembership = this.selectedMembershipState.asReadonly();

  load(): Observable<OrganizationMembership[]> {
    return this.http.get<OrganizationContextResponse>('/api/organizations/context/').pipe(
      map((response) => response.memberships),
      tap((memberships) => {
        const selectedMembershipId = this.selectedMembershipState()?.id ?? null;

        const selectedMembership =
          memberships.find((membership) => membership.id === selectedMembershipId) ??
          memberships[0] ??
          null;

        this.membershipsState.set(memberships);
        this.selectedMembershipState.set(selectedMembership);
      }),
    );
  }

  selectMembership(membershipId: number): void {
    const membership = this.membershipsState().find((item) => item.id === membershipId) ?? null;

    this.selectedMembershipState.set(membership);
  }

  clear(): void {
    this.membershipsState.set([]);
    this.selectedMembershipState.set(null);
  }
}
