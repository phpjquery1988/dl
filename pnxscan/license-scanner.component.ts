import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { ScanStep, ScanResult, LicenseData } from '../../models/license.model';
import { LicenseService } from '../../services/license.service';
import { CapturedImage } from './camera-view/camera-view.component';

@Component({
  selector: 'app-license-scanner',
  templateUrl: './license-scanner.component.html',
  styleUrls: ['./license-scanner.component.scss']
})
export class LicenseScannerComponent implements OnInit {
  ScanStep = ScanStep;
  currentStep: ScanStep = ScanStep.INTRO;

  frontCapture: CapturedImage | null = null;
  backCapture: CapturedImage | null = null;

  frontResult: ScanResult | null = null;
  backResult: ScanResult | null = null;
  finalResult: ScanResult | null = null;

  processingMessage = '';
  processingProgress = 0;
  errorMessage = '';

  constructor(
    private licenseService: LicenseService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {}

  startScan(): void {
    this.resetState();
    this.currentStep = ScanStep.FRONT_CAPTURE;
    this.cdr.detectChanges();
  }

  onFrontCaptured(image: CapturedImage): void {
    this.frontCapture = image;
    this.currentStep = ScanStep.FRONT_PREVIEW;
    this.cdr.detectChanges();
  }

  onBackCaptured(image: CapturedImage): void {
    this.backCapture = image;
    this.currentStep = ScanStep.BACK_PREVIEW;
    this.cdr.detectChanges();
  }

  retakeFront(): void {
    this.frontCapture = null;
    this.frontResult = null;
    this.currentStep = ScanStep.FRONT_CAPTURE;
  }

  retakeBack(): void {
    this.backCapture = null;
    this.backResult = null;
    this.currentStep = ScanStep.BACK_CAPTURE;
  }

  acceptFront(): void {
    this.currentStep = ScanStep.BACK_CAPTURE;
  }

  async processAll(): Promise<void> {
    if (!this.frontCapture || !this.backCapture) return;

    this.currentStep = ScanStep.PROCESSING;
    this.processingProgress = 0;
    this.processingMessage = 'Processing front side...';
    this.cdr.detectChanges();

    try {
      // Step 1: Process front (crop card)
      this.processingProgress = 20;
      const frontBlob = this.licenseService.dataURLtoBlob(this.frontCapture.dataUrl);
      
      this.frontResult = await this.licenseService.scanFront(frontBlob).toPromise() || null;
      this.processingProgress = 45;
      this.processingMessage = 'Scanning barcode on back side...';
      this.cdr.detectChanges();

      // Step 2: Process back (decode barcode)
      const backBlob = this.licenseService.dataURLtoBlob(this.backCapture.dataUrl);
      this.backResult = await this.licenseService.scanBack(backBlob).toPromise() || null;
      this.processingProgress = 75;
      this.processingMessage = 'Extracting license data...';
      this.cdr.detectChanges();

      await this.delay(500);
      this.processingProgress = 100;
      this.processingMessage = 'Complete!';

      // Build final result
      this.finalResult = {
        success: true,
        front_image: this.frontResult?.cropped_image || this.frontCapture.dataUrl,
        back_image: this.backResult?.barcode_image || this.backCapture.dataUrl,
        barcode_decoded: this.backResult?.success || false,
        barcode_type: this.backResult?.barcode_type || '',
        license_data: this.backResult?.parsed_data || {}
      };

      await this.delay(500);
      this.currentStep = ScanStep.RESULT;
      this.cdr.detectChanges();
    } catch (err: any) {
      this.errorMessage = err.message || 'Processing failed';
      this.currentStep = ScanStep.ERROR;
      this.cdr.detectChanges();
    }
  }

  scanAgain(): void {
    this.resetState();
    this.currentStep = ScanStep.INTRO;
  }

  private resetState(): void {
    this.frontCapture = null;
    this.backCapture = null;
    this.frontResult = null;
    this.backResult = null;
    this.finalResult = null;
    this.errorMessage = '';
    this.processingProgress = 0;
    this.processingMessage = '';
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  get stepIndex(): number {
    const steps = [ScanStep.FRONT_CAPTURE, ScanStep.BACK_CAPTURE, ScanStep.RESULT];
    return steps.indexOf(this.currentStep as any) + 1;
  }
}
