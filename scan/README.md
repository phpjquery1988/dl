# 🪪 DL Scanner — USA Driver License Reader

Full-stack Angular 19 + FastAPI application that scans both sides of any US driver license using your device camera. The front side is auto-cropped and perspective-corrected; the back side PDF417 barcode is decoded live using **ZXing** (Angular client) and server-side with **pyzbar + Tesseract OCR**.

---

## 📁 Project Structure

```
dl-scanner/
│
├── docker-compose.yml           ← Production compose (builds both images)
├── README.md
│
├── frontend/                    ← Angular 19 (standalone components)
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── angular.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── install.sh               ← Local setup script
│   └── src/
│       ├── main.ts              ← bootstrapApplication (standalone)
│       ├── index.html
│       ├── styles.scss          ← Global CSS variables + reset
│       ├── environments/
│       │   ├── environment.ts
│       │   └── environment.production.ts
│       └── app/
│           ├── app.component.ts     ← Root component (RouterOutlet)
│           ├── app.config.ts        ← provideRouter, provideHttpClient…
│           ├── app.routes.ts        ← Lazy-loads LicenseScannerComponent
│           ├── models/
│           │   └── license.model.ts ← All interfaces + ScanStep enum
│           ├── services/
│           │   └── license.service.ts
│           └── components/
│               └── license-scanner/
│                   ├── license-scanner.component.ts   ← Orchestration
│                   ├── license-scanner.component.html
│                   ├── license-scanner.component.scss
│                   ├── camera-view/                   ← Camera + ZXing
│                   │   ├── camera-view.component.ts
│                   │   ├── camera-view.component.html
│                   │   └── camera-view.component.scss
│                   └── scan-result/                   ← Results display
│                       ├── scan-result.component.ts
│                       ├── scan-result.component.html
│                       └── scan-result.component.scss
│
└── backend/                     ← FastAPI Python
    ├── Dockerfile
    ├── requirements.txt
    ├── install.sh               ← Local setup script
    └── main.py                  ← All endpoints + AAMVA parser + OCR
```

---

## 🚀 Quick Start

### Option A — Docker Compose (recommended)

```bash
# Clone / unzip the project
cd dl-scanner

# Build and start both services
docker-compose up --build

# Frontend → http://localhost:4200
# Backend  → http://localhost:8000
```

### Option B — Local Development

#### Backend

```bash
cd backend
chmod +x install.sh && ./install.sh

source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
chmod +x install.sh && ./install.sh

npm start
# → http://localhost:4200
```

> **HTTPS note:** Mobile browsers require HTTPS for camera access. Use `ngrok` or a self-signed cert for mobile dev testing. `localhost` works fine on desktop.

---

## 📱 Scan Flow

```
INTRO  →  FRONT CAPTURE  →  FRONT PREVIEW  →  BACK CAPTURE  →  BACK PREVIEW  →  PROCESSING  →  RESULT
```

| Step | What happens |
|------|-------------|
| **Front Capture** | `getUserMedia` rear camera opens. ZXing is not active. Canvas overlay draws card frame corners. |
| **Front Preview** | Shows the perspective-corrected `856×540` crop. User can retake or accept. |
| **Back Capture** | ZXing `BrowserMultiFormatReader` scans every 500 ms. Barcode zone is highlighted. Torch + zoom available. When ZXing finds the barcode, the shutter button turns green. |
| **Back Preview** | Shows the 2× upscaled barcode crop. Displays ZXing format if pre-detected. |
| **Processing** | Two API calls in sequence: `POST /scan/front` then `POST /scan/back`. |
| **Result** | Shows corrected front card image, barcode crop, and all AAMVA fields grouped by category. Export to JSON. |

---

## 📡 API Reference

### `GET /health`
```json
{ "status": "ok", "ts": "2025-01-01T00:00:00" }
```

---

### `POST /scan/front`

Accepts: `multipart/form-data` — field `file` (JPEG/PNG)

The Angular client sends the already perspective-cropped card region (client crops to the on-screen guide frame). The server applies a second-pass OpenCV perspective correction and runs Tesseract OCR.

**Response:**
```json
{
  "success": true,
  "cropped_image": "data:image/jpeg;base64,…",
  "ocr_fields": {
    "ocr_state": "CA",
    "ocr_license_number": "D1234567",
    "ocr_dob": "01/15/1990",
    "ocr_expiry": "01/15/2029"
  },
  "dimensions": { "width": 856, "height": 540 }
}
```

---

### `POST /scan/back`

Accepts: `multipart/form-data`
- `file` — barcode strip JPEG (2× upscaled)
- `raw_barcode_text` *(optional)* — ZXing pre-decoded text from client

**Decode priority:**
1. If `raw_barcode_text` contains AAMVA data → parse immediately (no image processing needed)
2. Server-side pyzbar across 7 preprocessed image variants
3. pdf417decoder fallback
4. Regional crop attempts (bottom half, top half, middle third)

**Response:**
```json
{
  "success": true,
  "source": "zxing_client",
  "barcode_type": "PDF417",
  "barcode_image": "data:image/jpeg;base64,…",
  "parsed_data": {
    "full_name": "JOHN A DOE",
    "license_number": "D1234567",
    "date_of_birth": "01/15/1990",
    "expiry_date": "01/15/2029",
    "sex": "Male",
    "height": "509",
    "eye_color": "Brown",
    "mailing_state": "CA",
    "full_address": "123 MAIN ST, ANYTOWN, CA, 90210",
    "…": "…"
  },
  "message": "Decoded by ZXing (client-side)"
}
```

---

## ⚙️ Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend framework** | Angular 19 — standalone components, signals, OnPush |
| **Barcode decode (client)** | `@zxing/browser` + `@zxing/library` |
| **Camera API** | `navigator.mediaDevices.getUserMedia` |
| **Torch / Zoom** | `MediaStreamTrack.applyConstraints({ torch, zoom })` |
| **Card crop** | Client-side canvas 2D — maps overlay frame to video pixels |
| **Backend** | FastAPI + uvicorn |
| **Barcode decode (server)** | pyzbar (primary) + pdf417decoder (fallback) |
| **Image preprocessing** | OpenCV — CLAHE, Canny, bilateral filter, perspective warp |
| **OCR** | Tesseract 5 via pytesseract |
| **AAMVA parsing** | Custom Python parser (150+ field codes) |
| **Containerization** | Docker + Docker Compose |
| **Nginx** | Serves Angular SPA + proxies `/api` → FastAPI |

---

## 🔧 Key Implementation Details

### Client-side Card Crop
`cropCardRegion()` in `camera-view.component.ts`:
- Maps the on-screen overlay frame coordinates (CSS pixels) to video pixel coordinates using `clientWidth/Height → videoWidth/Height` scale factors
- Draws the exact crop to an `856×540` output canvas (standard DL resolution)
- This is what gets sent to `POST /scan/front`

### Client-side Barcode Crop
`cropBarcodeRegion()`:
- Crops the bottom 35% of the card area where the PDF417 barcode lives on US licenses
- Upscales the crop 2× for better pyzbar decode on the server
- This is what gets sent to `POST /scan/back`

### ZXing Live Scanning (back mode)
- Runs every 500 ms via `setInterval` while camera is active
- Attempts full-frame decode first, then bottom-55% crop if that fails
- When barcode found: `barcodeDetected` signal set → overlay turns green, shutter pulses green
- Detected raw text stored and sent as `raw_barcode_text` to server → server skips image decode and just parses AAMVA fields

### Server Perspective Correction
`perspective_correct()` in `main.py`:
- Bilateral filter → Canny edge detection → dilation → contour finding → `approxPolyDP` for quad detection
- `getPerspectiveTransform` + `warpPerspective` to canonical `856×540` output
- Falls back to centre-crop with aspect-ratio preservation if no quad detected

---

## 📋 AAMVA Fields Decoded

The parser covers all standard AAMVA 2020 field codes including:

- **Personal:** Full name, first/middle/last, DOB, sex
- **License:** Number, class, restrictions, endorsements, issue/expiry dates
- **Address:** Mailing + residence (street, city, state, ZIP, country)
- **Physical:** Height, weight, eye color, hair color
- **Flags:** Organ donor, veteran, limited duration document
- **Age thresholds:** Under-18/19/21 until dates

---

## 🛡️ Privacy

- No images or personal data are persisted server-side
- All processing is in-memory; data is discarded after each API response
- For production: add HTTPS, authentication, and audit logging

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| Camera permission denied | Allow camera in browser settings → refresh |
| Torch not working | Only supported on Android Chrome; not available on iOS/desktop |
| Hardware zoom slider hidden | Device doesn't expose zoom capability; CSS-only zoom is used as fallback |
| Barcode not decoded | Ensure barcode area is fully lit, in focus, and not at an angle. Use torch + zoom. Try multiple times. |
| `pyzbar` install fails on macOS | `brew install zbar` first |
| `tesseract` not found | `sudo apt-get install tesseract-ocr` or `brew install tesseract` |
