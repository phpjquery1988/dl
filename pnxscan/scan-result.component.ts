import { Component, Input, Output, EventEmitter } from '@angular/core';
import { LicenseData } from '../../../models/license.model';

interface FieldGroup {
  label: string;
  icon: string;
  fields: { key: string; label: string; value: string }[];
}

@Component({
  selector: 'app-scan-result',
  templateUrl: './scan-result.component.html',
  styleUrls: ['./scan-result.component.scss']
})
export class ScanResultComponent {
  @Input() frontImage: string = '';
  @Input() backImage: string = '';
  @Input() licenseData: LicenseData = {};
  @Input() barcodeDecoded = false;
  @Input() barcodeType = '';

  @Output() scanAgain = new EventEmitter<void>();
  @Output() export = new EventEmitter<LicenseData>();

  get fieldGroups(): FieldGroup[] {
    const d = this.licenseData;
    const groups: FieldGroup[] = [];

    // Personal Info
    const personalFields = [
      { key: 'full_name', label: 'Full Name', value: d.full_name || '' },
      { key: 'first_name', label: 'First Name', value: d.first_name || d.first_name_full || '' },
      { key: 'middle_name', label: 'Middle Name', value: d.middle_name || '' },
      { key: 'last_name', label: 'Last Name', value: d.last_name || d.last_name_full || '' },
      { key: 'date_of_birth', label: 'Date of Birth', value: d.date_of_birth || '' },
      { key: 'sex', label: 'Sex', value: d.sex || '' },
    ].filter(f => f.value);

    if (personalFields.length) {
      groups.push({ label: 'Personal Information', icon: '👤', fields: personalFields });
    }

    // License Details
    const licenseFields = [
      { key: 'license_number', label: 'License Number', value: d.license_number || '' },
      { key: 'license_classification', label: 'Class', value: d.license_classification || '' },
      { key: 'license_restrictions', label: 'Restrictions', value: d.license_restrictions || '' },
      { key: 'license_endorsements', label: 'Endorsements', value: d.license_endorsements || '' },
      { key: 'issue_date', label: 'Issue Date', value: d.issue_date || '' },
      { key: 'expiry_date', label: 'Expiry Date', value: d.expiry_date || '' },
    ].filter(f => f.value);

    if (licenseFields.length) {
      groups.push({ label: 'License Details', icon: '🪪', fields: licenseFields });
    }

    // Physical Desc
    const physFields = [
      { key: 'height', label: 'Height', value: d.height || '' },
      { key: 'weight_lbs', label: 'Weight', value: d.weight_lbs ? `${d.weight_lbs} lbs` : '' },
      { key: 'eye_color', label: 'Eye Color', value: d.eye_color || '' },
      { key: 'hair_color', label: 'Hair Color', value: d.hair_color || '' },
    ].filter(f => f.value);

    if (physFields.length) {
      groups.push({ label: 'Physical Description', icon: '📏', fields: physFields });
    }

    // Address
    const addrFields = [
      { key: 'full_address', label: 'Address', value: d.full_address || '' },
      { key: 'mailing_city', label: 'City', value: d.mailing_city || d.residence_city || '' },
      { key: 'mailing_state', label: 'State', value: d.mailing_state || d.residence_state || '' },
      { key: 'mailing_postal_code', label: 'ZIP Code', value: d.mailing_postal_code || d.residence_postal_code || '' },
      { key: 'country_id', label: 'Country', value: d.country_id || '' },
    ].filter(f => f.value && f.key !== 'full_address' || f.key === 'full_address');
    
    const uniqueAddr = addrFields.filter(f => f.value);
    if (uniqueAddr.length) {
      groups.push({ label: 'Address', icon: '📍', fields: uniqueAddr });
    }

    // Other
    const otherFields = [
      { key: 'organ_donor', label: 'Organ Donor', value: d.organ_donor || '' },
      { key: 'veteran', label: 'Veteran', value: d.veteran || '' },
    ].filter(f => f.value);

    if (otherFields.length) {
      groups.push({ label: 'Additional Info', icon: 'ℹ️', fields: otherFields });
    }

    return groups;
  }

  get hasData(): boolean {
    return Object.keys(this.licenseData || {}).length > 0;
  }

  exportData(): void {
    this.export.emit(this.licenseData);
  }

  downloadJSON(): void {
    const data = JSON.stringify(this.licenseData, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `license_${this.licenseData.license_number || 'data'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
