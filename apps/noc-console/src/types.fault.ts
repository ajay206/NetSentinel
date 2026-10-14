export interface FaultPrediction {
  faultType: string;
  confidence: number;
  probabilities: Record<string, number>;
  modelVersion: string;
}

export interface ShapContribution {
  feature: string;
  value: number;
  shap: number;
}

export interface FaultExplanation {
  faultType: string;
  confidence: number;
  modelVersion: string;
  baseValue: number;
  contributions: ShapContribution[];
}

export const FAULT_LABELS: Record<string, string> = {
  fibre_cut: 'Fibre cut',
  power_failure: 'Power failure',
  cell_outage: 'Cell outage',
  congestion: 'Congestion',
  bad_upgrade: 'Bad upgrade',
  hw_drift: 'HW drift',
  core_packet_loss: 'Core packet loss',
};
