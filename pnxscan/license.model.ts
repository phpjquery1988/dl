export interface LicenseData {
  full_name?: string;
  first_name?: string;
  middle_name?: string;
  last_name?: string;
  date_of_birth?: string;
  expiry_date?: string;
  issue_date?: string;
  license_number?: string;
  license_classification?: string;
  license_restrictions?: string;
  license_endorsements?: string;
  sex?: string;
  height?: string;
  weight_lbs?: string;
  eye_color?: string;
  hair_color?: string;
  full_address?: string;
  mailing_street_1?: string;
  mailing_city?: string;
  mailing_state?: string;
  mailing_postal_code?: string;
  country_id?: string;
  document_discriminator?: string;
  organ_donor?: string;
  veteran?: string;
  [key: string]: string | undefined;
}

export interface ScanResult {
  success: boolean;
  message?: string;
  front_image?: string;
  back_image?: string;
  cropped_image?: string;
  barcode_image?: string;
  barcode_decoded?: boolean;
  barcode_type?: string;
  license_data?: LicenseData;
  parsed_data?: LicenseData;
  raw_data?: string;
  dimensions?: { width: number; height: number };
}

export enum ScanStep {
  INTRO = 'intro',
  FRONT_CAPTURE = 'front_capture',
  FRONT_PREVIEW = 'front_preview',
  BACK_CAPTURE = 'back_capture',
  BACK_PREVIEW = 'back_preview',
  PROCESSING = 'processing',
  RESULT = 'result',
  ERROR = 'error'
}

export interface CameraOptions {
  facingMode: 'environment' | 'user';
  zoom: number;
  torchEnabled: boolean;
  resolution: 'hd' | 'fhd' | '4k';
}
