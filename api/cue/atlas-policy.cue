package atlas.policy

// Contract-level policy vocabulary. Runtime evaluators must deny unknown
// fields and fail closed when this schema or its policy version is missing.
#ContractVersion: "1.0.0"

#TenantScope: {
  tenantId: string & != ""
  campusIds: [...#CampusId] & [_, ...]
}

#CampusId: string & != ""

#Purpose: {
  code: string & != ""
  businessContextId: string & != ""
  policyVersion: string & != ""
  consentVersion?: string
  emergency: bool
}

#AccessDecision: {
  allowed: bool
  policyVersion: string & != ""
  reasonCodes: [...string]
  traceId: string & != ""
}

#DenyByDefault: {
  if !AccessDecision.allowed {
    reasonCodes: [...string]
  }
}
