/** Step 21: GET /api/security/pqc */
export interface PqcTls {
  service: string;
  tls: boolean;
  hybrid: boolean;
  classical?: boolean;
  hybridOnly: boolean;
  group: string | null;
  target?: string;
  hybridDetail?: string;
}

export interface PqcModel {
  status: "pass" | "fail" | "unsigned" | "off" | "unknown";
  reason: string;
  alg?: string | null;
  keyId?: string | null;
  policy?: string;
  modelVersion?: string;
  verifiedAt?: string;
}

export interface PqcStatusResponse {
  checkedAt: string;
  tls: PqcTls[];
  model: PqcModel;
  report: string;
}
