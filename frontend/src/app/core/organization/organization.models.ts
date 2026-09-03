export type CompanyMembershipStatus = 'INVITED' | 'ACTIVE' | 'SUSPENDED' | 'LEFT';

export interface OrganizationCompany {
  id: number;
  name: string;
}

export interface OrganizationBranch {
  id: number;
  code: string;
  name: string;
}

export interface OrganizationMembership {
  id: number;
  status: CompanyMembershipStatus;
  company: OrganizationCompany;
  branches: OrganizationBranch[];
  permissions?: string[];
}

export interface OrganizationContextResponse {
  memberships: OrganizationMembership[];
}
