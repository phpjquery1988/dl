from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
import io
import re
from PIL import Image
import numpy as np
import cv2
from pyzbar.pyzbar import decode as pyzbar_decode
from pdf417decoder import PDF417Decoder
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="USA Driver License Scanner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AAMVA field mappings for USA Driver License
AAMVA_FIELD_MAP = {
    "DAA": "full_name",
    "DAB": "last_name",
    "DAC": "first_name",
    "DAD": "middle_name",
    "DAE": "name_suffix",
    "DAF": "name_prefix",
    "DAG": "mailing_street_1",
    "DAH": "mailing_street_2",
    "DAI": "mailing_city",
    "DAJ": "mailing_state",
    "DAK": "mailing_postal_code",
    "DAL": "residence_street_1",
    "DAM": "residence_street_2",
    "DAN": "residence_city",
    "DAO": "residence_state",
    "DAP": "residence_postal_code",
    "DAQ": "license_number",
    "DAR": "license_classification",
    "DAS": "license_restrictions",
    "DAT": "license_endorsements",
    "DAU": "height",
    "DAV": "weight_lbs",
    "DAW": "weight_kg",
    "DAX": "eye_color",
    "DAY": "hair_color",
    "DAZ": "ethnicity",
    "DBA": "expiry_date",
    "DBB": "date_of_birth",
    "DBC": "sex",
    "DBD": "issue_date",
    "DBE": "issue_timestamp",
    "DBF": "number_of_duplicates",
    "DBG": "medical_indicator_codes",
    "DBH": "organ_donor",
    "DBI": "non_resident",
    "DBJ": "customer_id_no",
    "DBK": "social_security_number",
    "DBL": "date_18",
    "DBM": "date_19",
    "DBN": "truncation_first",
    "DBO": "truncation_last",
    "DBP": "truncation_middle",
    "DBQ": "place_of_birth",
    "DCB": "hazmat_expiry",
    "DCD": "veteran",
    "DCF": "document_discriminator",
    "DCG": "country_id",
    "DCH": "federal_commercial",
    "DCI": "place_of_birth_ext",
    "DCJ": "audit_info",
    "DCK": "inventory_control",
    "DCL": "race_ethnicity",
    "DCM": "standard_vehicle_class",
    "DCN": "standard_endorsement_code",
    "DCO": "standard_restriction_code",
    "DCP": "jurisdiction_vehicle_classification",
    "DCQ": "jurisdiction_endorsement_code",
    "DCR": "jurisdiction_restriction_code",
    "DCS": "last_name_full",
    "DCT": "first_name_full",
    "DCU": "suffix",
    "DDA": "compliance_type",
    "DDB": "card_revision_date",
    "DDC": "hazmat_endorsement_expiry",
    "DDD": "limited_duration_document",
    "DDE": "weight_range",
    "DDF": "truncation_family",
    "DDG": "truncation_first_name",
    "DDH": "under_18_until",
    "DDI": "under_19_until",
    "DDJ": "under_21_until",
    "DDK": "organ_donor_2",
    "DDL": "veteran_2",
    "PAA": "permit_classification",
    "PAB": "permit_expiry",
    "PAC": "permit_id",
    "PAD": "permit_dob",
    "PAE": "permit_restrictions",
    "PAF": "permit_endorsements",
    "ZAA": "state_specific_1",
    "ZAB": "state_specific_2",
}

SEX_MAP = {"1": "Male", "2": "Female", "9": "Not Specified"}
EYE_COLOR_MAP = {
    "BLK": "Black", "BLU": "Blue", "BRO": "Brown", "GRY": "Gray",
    "GRN": "Green", "HAZ": "Hazel", "MAR": "Maroon", "PNK": "Pink",
    "DIC": "Dichromatic", "UNK": "Unknown"
}
HAIR_COLOR_MAP = {
    "BAL": "Bald", "BLK": "Black", "BLN": "Blond", "BRO": "Brown",
    "GRY": "Gray", "RED": "Red", "SDY": "Sandy", "WHI": "White", "UNK": "Unknown"
}


def parse_aamva_barcode(raw_data: str) -> dict:
    """Parse AAMVA PDF417 barcode data from US Driver License"""
    try:
        result = {}
        
        # Normalize line endings
        raw_data = raw_data.replace('\r\n', '\n').replace('\r', '\n')
        
        # Find subfile start (after header)
        # AAMVA header: @\n\x1e\rANSI ...
        lines = raw_data.split('\n')
        
        in_subfile = False
        for line in lines:
            line = line.strip()
            if line.startswith('DL') or line.startswith('ID'):
                in_subfile = True
                line = line[2:]  # Remove DL/ID prefix
            
            if not in_subfile:
                # Check if ANSI header line has data after it
                if 'ANSI ' in line or line.startswith('@'):
                    continue
            
            # Parse 3-char field codes
            i = 0
            while i < len(line) - 2:
                code = line[i:i+3]
                if code in AAMVA_FIELD_MAP:
                    # Find next code or end
                    next_pos = len(line)
                    for j in range(i + 3, len(line) - 2):
                        if line[j:j+3] in AAMVA_FIELD_MAP:
                            next_pos = j
                            break
                    
                    value = line[i+3:next_pos].strip()
                    if value:
                        field_name = AAMVA_FIELD_MAP[code]
                        result[field_name] = value
                    i = next_pos
                else:
                    i += 1
        
        # Post-process fields
        if 'sex' in result:
            result['sex'] = SEX_MAP.get(result['sex'], result['sex'])
        
        if 'eye_color' in result:
            result['eye_color'] = EYE_COLOR_MAP.get(result['eye_color'], result['eye_color'])
        
        if 'hair_color' in result:
            result['hair_color'] = HAIR_COLOR_MAP.get(result['hair_color'], result['hair_color'])
        
        # Format dates (MMDDYYYY -> MM/DD/YYYY)
        date_fields = ['date_of_birth', 'expiry_date', 'issue_date']
        for df in date_fields:
            if df in result and len(result[df]) == 8:
                d = result[df]
                result[df] = f"{d[0:2]}/{d[2:4]}/{d[4:8]}"
        
        # Build full address
        addr_parts = [
            result.get('mailing_street_1', result.get('residence_street_1', '')),
            result.get('mailing_street_2', result.get('residence_street_2', '')),
            result.get('mailing_city', result.get('residence_city', '')),
            result.get('mailing_state', result.get('residence_state', '')),
            result.get('mailing_postal_code', result.get('residence_postal_code', '')),
        ]
        addr_parts = [p for p in addr_parts if p]
        if addr_parts:
            result['full_address'] = ', '.join(addr_parts)
        
        # Build full name if not present
        if 'full_name' not in result:
            name_parts = [
                result.get('first_name', result.get('first_name_full', '')),
                result.get('middle_name', ''),
                result.get('last_name', result.get('last_name_full', '')),
                result.get('suffix', ''),
            ]
            name = ' '.join(p for p in name_parts if p)
            if name:
                result['full_name'] = name
        
        return result
    except Exception as e:
        logger.error(f"AAMVA parse error: {e}")
        return {}


def preprocess_barcode_image(img_array: np.ndarray) -> list:
    """Preprocess image to improve barcode detection"""
    variants = []
    
    # Convert to grayscale
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_array.copy()
    
    variants.append(gray)
    
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    variants.append(enhanced)
    
    # Threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(thresh)
    
    # Sharpen
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    variants.append(sharpened)
    
    # Scale up 2x
    scaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    variants.append(scaled)
    
    return variants


def decode_barcode_from_image(img_array: np.ndarray) -> dict | None:
    """Try to decode PDF417 barcode from image using multiple methods"""
    
    preprocessed = preprocess_barcode_image(img_array)
    
    for variant in preprocessed:
        pil_img = Image.fromarray(variant)
        barcodes = pyzbar_decode(pil_img)
        
        for barcode in barcodes:
            if barcode.type in ('PDF417', 'CODE128', 'CODE39', 'QRCODE', 'DATAMATRIX'):
                raw = barcode.data.decode('utf-8', errors='replace')
                if 'ANSI' in raw or 'DAQ' in raw or 'DBA' in raw:
                    parsed = parse_aamva_barcode(raw)
                    if parsed:
                        return {"raw": raw, "parsed": parsed, "barcode_type": barcode.type}
    
    # Try PDF417Decoder as fallback
    try:
        for variant in preprocessed:
            decoder = PDF417Decoder(Image.fromarray(variant))
            if decoder.decode() > 0:
                raw = decoder.barcode_data_index_to_string(0)
                if raw and ('ANSI' in raw or 'DAQ' in raw):
                    parsed = parse_aamva_barcode(raw)
                    if parsed:
                        return {"raw": raw, "parsed": parsed, "barcode_type": "PDF417"}
    except Exception as e:
        logger.warning(f"PDF417Decoder fallback failed: {e}")
    
    return None


def crop_card_from_image(img_array: np.ndarray) -> np.ndarray:
    """Auto-detect and crop license card from image"""
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    
    # Dilate edges
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    h, w = img_array.shape[:2]
    min_area = w * h * 0.1
    
    for contour in contours[:5]:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
            # Order points: TL, TR, BR, BL
            s = pts.sum(axis=1)
            diff = np.diff(pts, axis=1)
            tl = pts[np.argmin(s)]
            br = pts[np.argmax(s)]
            tr = pts[np.argmin(diff)]
            bl = pts[np.argmax(diff)]
            
            src = np.array([tl, tr, br, bl], dtype=np.float32)
            
            # Standard card ratio 85.6mm x 53.98mm ≈ 1.585
            card_w = int(max(
                np.linalg.norm(tr - tl),
                np.linalg.norm(br - bl)
            ))
            card_h = int(max(
                np.linalg.norm(bl - tl),
                np.linalg.norm(br - tr)
            ))
            
            dst = np.array([
                [0, 0], [card_w - 1, 0],
                [card_w - 1, card_h - 1], [0, card_h - 1]
            ], dtype=np.float32)
            
            M = cv2.getPerspectiveTransform(src, dst)
            warped = cv2.warpPerspective(img_array, M, (card_w, card_h))
            return warped
    
    # Return original if no card found
    return img_array


def numpy_to_base64(img_array: np.ndarray, format: str = "JPEG") -> str:
    pil = Image.fromarray(cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB) if len(img_array.shape) == 3 else img_array)
    buffer = io.BytesIO()
    pil.save(buffer, format=format, quality=90)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


@app.get("/")
async def root():
    return {"message": "USA Driver License Scanner API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/scan/front")
async def scan_front(file: UploadFile = File(...)):
    """Process front side of driver license - crop card and return"""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image")
        
        # Crop card
        cropped = crop_card_from_image(img)
        cropped_b64 = numpy_to_base64(cropped)
        
        h, w = cropped.shape[:2]
        
        return JSONResponse({
            "success": True,
            "message": "Front side processed successfully",
            "cropped_image": f"data:image/jpeg;base64,{cropped_b64}",
            "dimensions": {"width": w, "height": h}
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Front scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/back")
async def scan_back(file: UploadFile = File(...)):
    """Process back side of driver license - detect and decode PDF417 barcode"""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image")
        
        # Try to find and crop barcode region first
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Look for barcode region (usually lower half of back side)
        h, w = img.shape[:2]
        
        # Try full image first
        result = decode_barcode_from_image(img)
        
        if not result:
            # Try bottom half
            bottom_half = img[h//2:, :]
            result = decode_barcode_from_image(bottom_half)
        
        if not result:
            # Try top half
            top_half = img[:h//2, :]
            result = decode_barcode_from_image(top_half)
        
        # Crop just the barcode area for preview
        barcode_img_b64 = numpy_to_base64(img)  # Send full back image
        
        if result:
            return JSONResponse({
                "success": True,
                "message": "Barcode decoded successfully",
                "barcode_image": f"data:image/jpeg;base64,{barcode_img_b64}",
                "barcode_type": result.get("barcode_type", "PDF417"),
                "parsed_data": result.get("parsed", {}),
                "raw_data": result.get("raw", "")[:200]  # truncate for response
            })
        else:
            return JSONResponse({
                "success": False,
                "message": "Could not decode barcode. Please ensure good lighting and hold camera steady.",
                "barcode_image": f"data:image/jpeg;base64,{barcode_img_b64}",
                "parsed_data": {},
                "raw_data": ""
            })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Back scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/complete")
async def scan_complete(front: UploadFile = File(...), back: UploadFile = File(...)):
    """Process both sides together and return complete driver license data"""
    try:
        # Process front
        front_contents = await front.read()
        front_nparr = np.frombuffer(front_contents, np.uint8)
        front_img = cv2.imdecode(front_nparr, cv2.IMREAD_COLOR)
        front_cropped = crop_card_from_image(front_img)
        front_b64 = numpy_to_base64(front_cropped)
        
        # Process back
        back_contents = await back.read()
        back_nparr = np.frombuffer(back_contents, np.uint8)
        back_img = cv2.imdecode(back_nparr, cv2.IMREAD_COLOR)
        
        barcode_result = decode_barcode_from_image(back_img)
        if not barcode_result:
            h = back_img.shape[0]
            barcode_result = decode_barcode_from_image(back_img[h//2:, :])
        
        back_b64 = numpy_to_base64(back_img)
        
        return JSONResponse({
            "success": True,
            "front_image": f"data:image/jpeg;base64,{front_b64}",
            "back_image": f"data:image/jpeg;base64,{back_b64}",
            "barcode_decoded": barcode_result is not None,
            "license_data": barcode_result.get("parsed", {}) if barcode_result else {},
            "barcode_type": barcode_result.get("barcode_type") if barcode_result else None,
        })
    except Exception as e:
        logger.error(f"Complete scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
