import {
  Component, OnInit, OnDestroy, Output, EventEmitter,
  Input, ElementRef, ViewChild, ChangeDetectorRef, NgZone
} from '@angular/core';
import { CameraOptions } from '../../../models/license.model';

export interface CapturedImage {
  dataUrl: string;
  blob: Blob;
  width: number;
  height: number;
}

@Component({
  selector: 'app-camera-view',
  templateUrl: './camera-view.component.html',
  styleUrls: ['./camera-view.component.scss']
})
export class CameraViewComponent implements OnInit, OnDestroy {
  @Input() mode: 'front' | 'back' = 'front';
  @Input() title = 'Position your ID card';
  @Input() subtitle = 'Align card within the frame';

  @Output() imageCaptured = new EventEmitter<CapturedImage>();
  @Output() cameraError = new EventEmitter<string>();

  @ViewChild('videoEl') videoRef!: ElementRef<HTMLVideoElement>;
  @ViewChild('canvasEl') canvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('overlayCanvas') overlayRef!: ElementRef<HTMLCanvasElement>;

  stream: MediaStream | null = null;
  isStreamActive = false;
  isCapturing = false;
  flashActive = false;
  permissionDenied = false;
  cameraErrorMsg = '';
  countdownValue = 0;
  isCountingDown = false;

  // Camera controls
  zoomLevel = 1;
  minZoom = 1;
  maxZoom = 5;
  torchEnabled = false;
  torchSupported = false;
  currentFacingMode: 'environment' | 'user' = 'environment';

  // Track for barcode region hint (back only)
  barcodeRegionVisible = false;

  private animFrameId: number | null = null;
  private countdownTimer: any;
  private track: MediaStreamTrack | null = null;

  constructor(private cdr: ChangeDetectorRef, private zone: NgZone) {}

  ngOnInit(): void {
    this.startCamera();
  }

  ngOnDestroy(): void {
    this.stopCamera();
    if (this.countdownTimer) clearInterval(this.countdownTimer);
    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
  }

  async startCamera(): Promise<void> {
    try {
      this.cameraErrorMsg = '';
      this.permissionDenied = false;

      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: { ideal: this.currentFacingMode },
          width: { ideal: 1920, min: 1280 },
          height: { ideal: 1080, min: 720 },
          frameRate: { ideal: 30 }
        },
        audio: false
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      const video = this.videoRef?.nativeElement;
      if (video) {
        video.srcObject = this.stream;
        await video.play();
        this.isStreamActive = true;

        // Get track for zoom/torch
        this.track = this.stream.getVideoTracks()[0];
        await this.initTrackCapabilities();

        this.cdr.detectChanges();
      }
    } catch (err: any) {
      this.zone.run(() => {
        if (err.name === 'NotAllowedError') {
          this.permissionDenied = true;
          this.cameraErrorMsg = 'Camera permission denied. Please allow camera access.';
        } else if (err.name === 'NotFoundError') {
          this.cameraErrorMsg = 'No camera found on this device.';
        } else {
          this.cameraErrorMsg = `Camera error: ${err.message}`;
        }
        this.cameraError.emit(this.cameraErrorMsg);
        this.cdr.detectChanges();
      });
    }
  }

  private async initTrackCapabilities(): Promise<void> {
    if (!this.track) return;
    try {
      const capabilities = this.track.getCapabilities() as any;
      
      if (capabilities.zoom) {
        this.minZoom = capabilities.zoom.min || 1;
        this.maxZoom = capabilities.zoom.max || 5;
        this.zoomLevel = this.minZoom;
      }

      if (capabilities.torch) {
        this.torchSupported = true;
      }
      this.cdr.detectChanges();
    } catch (e) {
      // Capabilities not supported
    }
  }

  async setZoom(value: number): Promise<void> {
    this.zoomLevel = Math.max(this.minZoom, Math.min(this.maxZoom, value));
    if (this.track) {
      try {
        await (this.track as any).applyConstraints({ advanced: [{ zoom: this.zoomLevel }] });
      } catch (e) {
        // Zoom not supported, use CSS transform
        const video = this.videoRef?.nativeElement;
        if (video) {
          video.style.transform = `scale(${this.zoomLevel})`;
          video.style.transformOrigin = 'center center';
        }
      }
    }
    this.cdr.detectChanges();
  }

  async toggleTorch(): Promise<void> {
    if (!this.track || !this.torchSupported) return;
    try {
      this.torchEnabled = !this.torchEnabled;
      await (this.track as any).applyConstraints({
        advanced: [{ torch: this.torchEnabled }]
      });
      this.cdr.detectChanges();
    } catch (e) {
      this.torchEnabled = false;
    }
  }

  onZoomChange(event: Event): void {
    const val = parseFloat((event.target as HTMLInputElement).value);
    this.setZoom(val);
  }

  captureWithCountdown(): void {
    if (this.isCountingDown || this.isCapturing) return;
    this.countdownValue = 3;
    this.isCountingDown = true;
    this.cdr.detectChanges();

    this.countdownTimer = setInterval(() => {
      this.countdownValue--;
      if (this.countdownValue <= 0) {
        clearInterval(this.countdownTimer);
        this.isCountingDown = false;
        this.captureImage();
      }
      this.cdr.detectChanges();
    }, 1000);
  }

  captureImage(): void {
    if (this.isCapturing) return;
    const video = this.videoRef?.nativeElement;
    const canvas = this.canvasRef?.nativeElement;
    if (!video || !canvas) return;

    this.isCapturing = true;
    this.flashActive = true;
    this.cdr.detectChanges();

    setTimeout(() => { this.flashActive = false; this.cdr.detectChanges(); }, 200);

    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;

    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // If back mode, optionally crop to barcode region
    let finalCanvas = canvas;
    if (this.mode === 'back') {
      // Crop lower 50% where PDF417 barcode typically is on US DL
      const barcodeCanvas = document.createElement('canvas');
      barcodeCanvas.width = canvas.width;
      barcodeCanvas.height = Math.floor(canvas.height * 0.6);
      const bCtx = barcodeCanvas.getContext('2d')!;
      bCtx.drawImage(canvas,
        0, Math.floor(canvas.height * 0.4),
        canvas.width, Math.floor(canvas.height * 0.6),
        0, 0,
        barcodeCanvas.width, barcodeCanvas.height
      );
      finalCanvas = barcodeCanvas;
    }

    finalCanvas.toBlob((blob) => {
      if (blob) {
        const dataUrl = finalCanvas.toDataURL('image/jpeg', 0.92);
        this.imageCaptured.emit({
          dataUrl,
          blob,
          width: finalCanvas.width,
          height: finalCanvas.height
        });
      }
      this.isCapturing = false;
      this.cdr.detectChanges();
    }, 'image/jpeg', 0.92);
  }

  stopCamera(): void {
    if (this.torchEnabled && this.track) {
      try { (this.track as any).applyConstraints({ advanced: [{ torch: false }] }); } catch (_) {}
    }
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    const video = this.videoRef?.nativeElement;
    if (video) video.srcObject = null;
    this.isStreamActive = false;
  }

  flipCamera(): void {
    this.currentFacingMode = this.currentFacingMode === 'environment' ? 'user' : 'environment';
    this.stopCamera();
    setTimeout(() => this.startCamera(), 300);
  }
}
