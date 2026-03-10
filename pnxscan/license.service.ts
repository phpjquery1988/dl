import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { ScanResult } from '../models/license.model';

@Injectable({
  providedIn: 'root'
})
export class LicenseService {
  private apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  scanFront(imageBlob: Blob): Observable<ScanResult> {
    const formData = new FormData();
    formData.append('file', imageBlob, 'front.jpg');
    return this.http.post<ScanResult>(`${this.apiUrl}/scan/front`, formData)
      .pipe(catchError(this.handleError));
  }

  scanBack(imageBlob: Blob): Observable<ScanResult> {
    const formData = new FormData();
    formData.append('file', imageBlob, 'back.jpg');
    return this.http.post<ScanResult>(`${this.apiUrl}/scan/back`, formData)
      .pipe(catchError(this.handleError));
  }

  scanComplete(frontBlob: Blob, backBlob: Blob): Observable<ScanResult> {
    const formData = new FormData();
    formData.append('front', frontBlob, 'front.jpg');
    formData.append('back', backBlob, 'back.jpg');
    return this.http.post<ScanResult>(`${this.apiUrl}/scan/complete`, formData)
      .pipe(catchError(this.handleError));
  }

  /**
   * Convert base64 data URL to Blob
   */
  dataURLtoBlob(dataURL: string): Blob {
    const arr = dataURL.split(',');
    const mime = arr[0].match(/:(.*?);/)![1];
    const bstr = atob(arr[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) u8arr[n] = bstr.charCodeAt(n);
    return new Blob([u8arr], { type: mime });
  }

  private handleError(error: any): Observable<never> {
    let message = 'An unknown error occurred';
    if (error.error?.detail) message = error.error.detail;
    else if (error.message) message = error.message;
    return throwError(() => new Error(message));
  }
}
