# 🪪 USA Driver License Scanner

A full-stack Angular + FastAPI application to scan and extract data from US Driver Licenses. Captures front (cropped card) and back (PDF417 barcode decoded) using your device camera with torch and zoom controls.

---

## 🏗️ Architecture

```
dl-scanner/
├── frontend/          # Angular 17 app
│   ├── src/app/
│   │   ├── components/
│   │   │   └── license-scanner/
│   │   │       ├── camera-view/       # Camera with zoom/torch
│   │   │       ├── scan-result/       # Results display
│   │   │       └── license-scanner/   # Main orchestration
│   │   ├── services/
│   │   │   └── license.service.ts     # API calls
│   │   └── models/
│   │       └── license.model.ts       # TypeScript interfaces
│   └── ...
└── backend/           # FastAPI Python
    ├── main.py        # All API endpoints + AAMVA parser
    ├── requirements.txt
    └── Dockerfile
```

---

## 🚀 Quick Start

### Option A: Docker Compose (Recommended)

```bash
docker-compose up --build
```
- Frontend: http://localhost:4200  
- Backend: http://localhost:8000

### Option B: Manual Setup

#### Backend (Python 3.10+)

```bash
cd backend

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y libzbar0 libzbar-dev libgl1

# Install Python packages
pip install -r requirements.txt

# Run
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend (Node 18+)

```bash
cd frontend

# Install Angular CLI globally (optional)
npm install -g @angular/cli

# Install dependencies
npm install

# Start dev server
ng serve --open
# or: npm start
```

---

## 📡 API Endpoints

### `POST /scan/front`
Processes front side image — auto-detects and perspective-crops the card.

**Request:** `multipart/form-data` with field `file` (image)

**Response:**
```json
{
  "success": true,
  "cropped_image": "data:image/jpeg;base64,...",
  "dimensions": { "width": 856, "height": 540 }
}
```

---

### `POST /scan/back`
Processes back side image — decodes PDF417 barcode using AAMVA spec.

**Request:** `multipart/form-data` with field `file` (image)

**Response:**
```json
{
  "success": true,
  "barcode_type": "PDF417",
  "barcode_image": "data:image/jpeg;base64,...",
  "parsed_data": {
    "full_name": "JOHN DOE",
    "date_of_birth": "01/15/1990",
    "license_number": "D1234567",
    "expiry_date": "01/15/2029",
    "mailing_state": "CA",
    ...
  }
}
```

---

### `POST /scan/complete`
Processes both sides in one request.

**Request:** `multipart/form-data` with fields `front` and `back`

---

## 📱 Frontend Features

### Camera View (`camera-view.component`)
- **`ngx-cam-shoot` integration** via native `getUserMedia` API
- **Torch/Flashlight** toggle — uses `MediaStreamTrack.applyConstraints({ torch: true })`
- **Hardware zoom** — uses `MediaStreamTrack.applyConstraints({ zoom: N })`
- **CSS zoom fallback** if hardware zoom unavailable
- **Rear camera** (`facingMode: environment`) preferred for scanning
- **Camera flip** button
- **Card frame overlay** with animated corner guides
- **Back mode**: scan-line animation + barcode zone indicator
- **Flash effect** on capture

### Scan Flow
1. **Intro** → Instructions + step preview
2. **Front Capture** → Camera + card frame overlay
3. **Front Preview** → Review or retake
4. **Back Capture** → Camera + barcode zone hint + torch
5. **Back Preview** → Review or retake
6. **Processing** → Animated progress with live messages
7. **Result** → Grouped field display + images + JSON export

---

## 🔬 Barcode Decoding (AAMVA PDF417)

The backend decodes **AAMVA-standard PDF417** barcodes found on all US/Canada driver licenses.

Libraries used:
- **pyzbar** — primary decoder
- **pdf417decoder** — fallback decoder
- **OpenCV** — preprocessing (CLAHE, sharpening, scaling, thresholding)

Preprocessing pipeline:
1. Grayscale conversion
2. CLAHE histogram equalization
3. Otsu's binarization
4. Sharpening kernel
5. 2× upscaling

Fields decoded from AAMVA spec (150+ fields including):
- Full name, DOB, sex
- License number, class, restrictions
- Address (mailing + residence)
- Physical: height, weight, eye color, hair color
- Issue/expiry dates
- Organ donor, veteran status
- And many more...

---

## ⚠️ Notes

- **HTTPS required** for camera access on mobile devices in production
- Use a valid SSL certificate or a reverse proxy (nginx + Let's Encrypt)
- For local testing, `localhost` is treated as secure by browsers
- Torch support varies by device/browser (best on Android Chrome)
- Hardware zoom is supported on Android Chrome; iOS uses CSS zoom fallback

---

## 🔒 Privacy

- No images are stored server-side; all processing is in-memory
- All data is discarded after API response
- For production, add authentication and HTTPS

---

## 📦 Dependencies

### Frontend
| Package | Purpose |
|---------|---------|
| `@angular/core` v17 | Framework |
| Native `getUserMedia` | Camera stream (replaces `ngx-cam-shoot` lower-level) |

### Backend
| Package | Purpose |
|---------|---------|
| `fastapi` | REST API |
| `opencv-python-headless` | Image preprocessing |
| `pyzbar` | PDF417/barcode decoding |
| `pdf417decoder` | Fallback barcode decoder |
| `Pillow` | Image conversion |
| `numpy` | Array operations |
