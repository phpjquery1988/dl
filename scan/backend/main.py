"""
DL Scanner — FastAPI Backend v3.2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Frontend now sends a guide-frame-cropped 856×540 card image.
Python focuses entirely on:
  1. Deskewing residual tilt
  2. Multi-pass barcode decoding with aggressive preprocessing
"""
from __future__ import annotations
import base64, io, logging, math, re
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode
import rembg

# Optional decoders — gracefully degrade if not installed
try:
    from pdf417decoder import PDF417Decoder
    _HAS_PDF417 = True
except ImportError:
    _HAS_PDF417 = False

try:
    import zxingcpp          # pip install zxing-cpp  (best PDF417 decoder)
    _HAS_ZXING = True
except ImportError:
    _HAS_ZXING = False

try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:
    _HAS_TESSERACT = False

log = logging.getLogger("dl-scanner")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

CARD_W, CARD_H = 856, 540
CARD_RATIO     = CARD_W / CARD_H

# ═══════════════════════════════════════════════════════════════
app = FastAPI(title="DL Scanner API", version="3.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
#  AAMVA PARSER
# ═══════════════════════════════════════════════════════════════
AAMVA: dict[str,str] = {
    "DAA":"full_name","DAB":"last_name","DAC":"first_name","DAD":"middle_name",
    "DAE":"name_suffix","DCS":"last_name_full","DCT":"first_name_full",
    "DAG":"mailing_street_1","DAH":"mailing_street_2","DAI":"mailing_city",
    "DAJ":"mailing_state","DAK":"mailing_postal_code",
    "DAL":"residence_street_1","DAM":"residence_street_2","DAN":"residence_city",
    "DAO":"residence_state","DAP":"residence_postal_code",
    "DAQ":"license_number","DAR":"license_classification",
    "DAS":"license_restrictions","DAT":"license_endorsements",
    "DCF":"document_discriminator","DCG":"country_id",
    "DDA":"compliance_type","DDB":"card_revision_date","DDD":"limited_duration",
    "DAU":"height","DAW":"weight_lbs","DAX":"eye_color","DAY":"hair_color",
    "DBC":"sex","DBA":"expiry_date","DBB":"date_of_birth","DBD":"issue_date",
    "DDH":"under_18_until","DDI":"under_19_until","DDJ":"under_21_until",
    "DBH":"organ_donor","DDL":"veteran",
}
_SEX  = {"1":"Male","2":"Female","9":"Not Specified"}
_EYES = {"BLK":"Black","BLU":"Blue","BRO":"Brown","GRY":"Gray","GRN":"Green",
         "HAZ":"Hazel","MAR":"Maroon","UNK":"Unknown"}
_HAIR = {"BAL":"Bald","BLK":"Black","BLN":"Blond","BRO":"Brown","GRY":"Gray",
         "RED":"Red","SDY":"Sandy","WHI":"White","UNK":"Unknown"}

def _fmtdate(s: str) -> str:
    d = re.sub(r"\D","",s)
    if len(d)==8:
        if 1900<=int(d[:4])<=2100 and int(d[4:6])<=12:
            return f"{d[4:6]}/{d[6:8]}/{d[:4]}"
        return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return s

def parse_aamva(raw: str) -> dict:
    if not raw: return {}
    res: dict[str,str] = {}
    raw = raw.replace("\r\n","\n").replace("\r","\n")
    in_dl = False
    for line in raw.split("\n"):
        s = line.strip()
        if not s: continue
        if s.startswith(("DL","ID")): in_dl=True; s=s[2:]
        if not in_dl and "ANSI" not in s: continue
        i=0
        while i<=len(s)-3:
            code=s[i:i+3]
            if code in AAMVA:
                end=len(s)
                for j in range(i+3,len(s)-2):
                    if s[j:j+3] in AAMVA: end=j; break
                val=s[i+3:end].strip()
                if val: res[AAMVA[code]]=val
                i=end
            else: i+=1
    res["sex"]       = _SEX.get(res.get("sex",""),       res.get("sex",""))
    res["eye_color"] = _EYES.get(res.get("eye_color",""),res.get("eye_color",""))
    res["hair_color"]= _HAIR.get(res.get("hair_color",""),res.get("hair_color",""))
    for f in ("date_of_birth","expiry_date","issue_date","card_revision_date",
              "under_18_until","under_19_until","under_21_until"):
        if f in res: res[f]=_fmtdate(res[f])
    if "full_name" not in res:
        parts=[res.get("first_name") or res.get("first_name_full",""),
               res.get("middle_name",""),
               res.get("last_name")  or res.get("last_name_full","")]
        name=" ".join(p for p in parts if p)
        if name: res["full_name"]=name
    addr=", ".join(p for p in [
        res.get("mailing_street_1") or res.get("residence_street_1",""),
        res.get("mailing_city")     or res.get("residence_city",""),
        res.get("mailing_state")    or res.get("residence_state",""),
        res.get("mailing_postal_code") or res.get("residence_postal_code",""),
    ] if p)
    if addr: res["full_address"]=addr
    return {k:v for k,v in res.items() if v}


# ═══════════════════════════════════════════════════════════════
#  UTILS
# ═══════════════════════════════════════════════════════════════
def _load(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data,np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400,"Cannot decode image.")
    return img

def _b64(img: np.ndarray, q: int=88) -> str:
    buf=io.BytesIO()
    Image.fromarray(cv2.cvtColor(img,cv2.COLOR_BGR2RGB)).save(buf,"JPEG",quality=q,optimize=True)
    return base64.b64encode(buf.getvalue()).decode()

def _ensure_856x540(img: np.ndarray) -> np.ndarray:
    """Resize/pad image to standard card size if needed."""
    h,w = img.shape[:2]
    if w==CARD_W and h==CARD_H: return img
    return cv2.resize(img,(CARD_W,CARD_H),interpolation=cv2.INTER_LANCZOS4)


# ═══════════════════════════════════════════════════════════════
#  DESKEW
#  The card may have residual tilt even after the frontend crop.
#  Detect the dominant horizontal angle via Hough lines and correct it.
# ═══════════════════════════════════════════════════════════════
def deskew(card: np.ndarray) -> tuple[np.ndarray, float]:
    h,w = card.shape[:2]
    gray = cv2.cvtColor(card,cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(2.0,(8,8))
    edges = cv2.Canny(clahe.apply(gray),40,120,apertureSize=3)

    lines = cv2.HoughLinesP(edges,1,np.pi/180,threshold=60,
                            minLineLength=int(w*0.20),maxLineGap=25)
    if lines is None: return card, 0.0

    angles=[]
    for line in lines:
        x1,y1,x2,y2 = line[0]
        dx,dy = x2-x1,y2-y1
        if abs(dx)<1: continue
        a = math.degrees(math.atan2(dy,dx))
        if abs(a)<=20: angles.append(a)

    if not angles: return card,0.0
    med = float(np.median(angles))
    if abs(med)<0.8 or abs(med)>20: return card,0.0

    M = cv2.getRotationMatrix2D((w//2,h//2),med,1.0)
    rotated = cv2.warpAffine(card,M,(w,h),
                              flags=cv2.INTER_LANCZOS4,
                              borderMode=cv2.BORDER_REPLICATE)
    log.info("Deskew: %.1f°",med)
    return rotated,med

def crop_card(img: np.ndarray) -> np.ndarray:
    """
    Use rembg to remove the background (e.g., face, fingers), finding the
    largest contour in the mask, and warping it to an 856x540 perspective.
    """
    try:
        # Get binary mask of the ID card
        mask = rembg.remove(img, only_mask=True)
        
        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img
            
        # Get the largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Approximate the contour to a polygon
        peri = cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, 0.02 * peri, True)
        
        if len(approx) == 4:
            pts = approx.reshape(4, 2)
        else:
            rect = cv2.minAreaRect(largest_contour)
            box = cv2.boxPoints(rect)
            pts = np.int32(box)
            
        # Order the points: top-left, top-right, bottom-right, bottom-left
        rect_pts = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect_pts[0] = pts[np.argmin(s)]
        rect_pts[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect_pts[1] = pts[np.argmin(diff)]
        rect_pts[3] = pts[np.argmax(diff)]
        
        # Ensure the ordered points match a landscape card orientation (wider than tall)
        width_top = np.linalg.norm(rect_pts[0] - rect_pts[1])
        height_left = np.linalg.norm(rect_pts[0] - rect_pts[3])
        if height_left > width_top:
            # Shift points to rotate 90 degrees
            rect_pts = np.roll(rect_pts, 1, axis=0)

        # Target dimensions for the card
        dst = np.array([
            [0, 0],
            [CARD_W - 1, 0],
            [CARD_W - 1, CARD_H - 1],
            [0, CARD_H - 1]
        ], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect_pts, dst)
        warped = cv2.warpPerspective(img, M, (CARD_W, CARD_H), flags=cv2.INTER_LANCZOS4)
        log.info("crop_card: Successful perspective crop using rembg mask.")
        return warped
    except Exception as e:
        log.error("crop_card error: %s", str(e))
        return img


# ═══════════════════════════════════════════════════════════════
#  PREPROCESSING VARIANTS
#
#  15 variants ordered best-first for real camera photos of glossy
#  ID cards (low contrast, reflections, slight blur).
# ═══════════════════════════════════════════════════════════════
def make_variants(img: np.ndarray) -> list[np.ndarray]:
    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY) if img.ndim==3 else img.copy()
    h,w  = gray.shape

    clahe3 = cv2.createCLAHE(3.0,(8,8))
    clahe4 = cv2.createCLAHE(4.0,(4,4))
    cg3    = clahe3.apply(gray)
    cg4    = clahe4.apply(gray)

    # Adaptive threshold variants — best for glossy cards
    adp21 = cv2.adaptiveThreshold(cg3,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,21,4)
    adp15 = cv2.adaptiveThreshold(cg3,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,15,3)
    adp31 = cv2.adaptiveThreshold(cg3,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,5)

    # Otsu on CLAHE
    _,otsu3 = cv2.threshold(cg3,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    _,otsu4 = cv2.threshold(cg4,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    # Contrast stretch (min-max normalise)
    mn,mx = gray.min(),gray.max()
    stretch = np.clip((gray.astype(float)-mn)/max(mx-mn,1)*255,0,255).astype(np.uint8)
    _,s_bin = cv2.threshold(clahe3.apply(stretch),0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    # 2× upscale variants — more pixels helps low-resolution barcodes
    up2     = cv2.resize(gray,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
    up2_c   = clahe3.apply(up2)
    up2_adp = cv2.adaptiveThreshold(up2_c,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,21,4)
    _,up2_ot= cv2.threshold(up2_c,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    # Sharpen then CLAHE
    k = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
    sharp = clahe3.apply(cv2.filter2D(gray,-1,k))

    # Bilateral filter (noise removal, edge preservation) + Otsu
    bilat = cv2.bilateralFilter(gray,9,75,75)
    _,bil_ot = cv2.threshold(clahe3.apply(bilat),0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    # Invert (some scanners prefer white bars on black)
    inv    = cv2.bitwise_not(adp21)
    inv_up = cv2.bitwise_not(up2_adp)

    return [adp21, up2_adp, up2_ot, adp15, adp31, otsu3, otsu4,
            s_bin, up2_c, sharp, cg3, gray, bil_ot, inv, inv_up]


# ═══════════════════════════════════════════════════════════════
#  DECODER WRAPPERS
# ═══════════════════════════════════════════════════════════════
def _decode_pyzbar(v: np.ndarray) -> dict|None:
    for bc in pyzbar_decode(Image.fromarray(v)):
        try: raw=bc.data.decode("utf-8","replace")
        except: continue
        if "ANSI" in raw or "DAQ" in raw or "DBA" in raw:
            p=parse_aamva(raw)
            if p: return {"raw":raw,"parsed":p,"type":str(bc.type)}
    return None

def _decode_pdf417lib(v: np.ndarray) -> dict|None:
    if not _HAS_PDF417: return None
    try:
        d=PDF417Decoder(Image.fromarray(v))
        if d.decode()>0:
            raw=d.barcode_data_index_to_string(0)
            if raw and ("ANSI" in raw or "DAQ" in raw):
                p=parse_aamva(raw)
                if p: return {"raw":raw,"parsed":p,"type":"PDF417"}
    except: pass
    return None

def _decode_zxingcpp(v: np.ndarray) -> dict|None:
    """zxing-cpp — best Python PDF417 decoder.  pip install zxing-cpp"""
    if not _HAS_ZXING: return None
    try:
        results = zxingcpp.read_barcodes(Image.fromarray(v))
        for r in results:
            raw = r.text
            if raw and ("ANSI" in raw or "DAQ" in raw or "DBA" in raw):
                p = parse_aamva(raw)
                if p: return {"raw":raw,"parsed":p,"type":str(r.format)}
    except: pass
    return None

def _try_all_decoders(v: np.ndarray) -> dict|None:
    # zxing-cpp first (most capable)
    r = _decode_zxingcpp(v)
    if r: return r
    r = _decode_pyzbar(v)
    if r: return r
    return _decode_pdf417lib(v)


# ═══════════════════════════════════════════════════════════════
#  BARCODE BAND AUTO-DETECTION
# ═══════════════════════════════════════════════════════════════
def detect_barcode_band(gray: np.ndarray) -> tuple[int,int]|None:
    h,w  = gray.shape
    rdark= (gray<128).mean(axis=1)
    rvar = gray.astype(float).var(axis=1)
    mask = (rvar>1000) & (rdark>0.15) & (rdark<0.85)
    if mask.sum()<8: return None
    rows=np.where(mask)[0]
    bs=be=bl=0; cs=cp=rows[0]
    for r in rows[1:]:
        if r-cp>10:
            if cp-cs>bl: bl,bs,be=cp-cs,cs,cp
            cs=r
        cp=r
    if cp-cs>bl: bs,be=cs,cp
    if be-bs<15: return None
    pad=max(10,(be-bs)//6)
    return max(0,bs-pad),min(h,be+pad)


# ═══════════════════════════════════════════════════════════════
#  FULL BARCODE DECODE PIPELINE
#
#  Frontend now sends a guide-cropped 856×540 card image, so we
#  focus entirely on robust barcode extraction from the card.
#
#  Pass 1  — full card, all 15 preprocessing variants
#  Pass 2  — auto-detected barcode band
#  Pass 3  — 8 overlapping horizontal bands (top→bottom)
#  Pass 4  — fine rotations ±3°…±20° (residual tilt)
#  Pass 5  — 90°/270° (landscape card)
# ═══════════════════════════════════════════════════════════════
def decode_barcode(card: np.ndarray) -> dict|None:
    gray = cv2.cvtColor(card,cv2.COLOR_BGR2GRAY) if card.ndim==3 else card.copy()
    h,w  = gray.shape

    def try_region(region: np.ndarray, label: str) -> dict|None:
        for v in make_variants(region):
            r = _try_all_decoders(v)
            if r:
                log.info("Barcode decoded  label=%s  type=%s  fields=%d",
                         label, r["type"], len(r["parsed"]))
                return r
        return None

    # Pass 1 — full card
    res = try_region(card,"full")
    if res: return res

    # Pass 2 — auto-detected band
    band = detect_barcode_band(gray)
    if band:
        y0,y1 = band
        res = try_region(card[y0:y1,:],"auto_band")
        if res: return res

    # Pass 3 — 8 overlapping bands covering 0–100%
    # Same band layout as the frontend's ZXing scan loop
    bands = [
        ("top40",   0,          int(h*.40)),
        ("up",      int(h*.05), int(h*.48)),
        ("umid",    int(h*.20), int(h*.60)),
        ("mid",     int(h*.35), int(h*.72)),
        ("lmid",    int(h*.48), int(h*.85)),
        ("bot40",   int(h*.60), h),
        ("thalf",   0,          int(h*.55)),
        ("bhalf",   int(h*.45), h),
    ]
    for label,y0,y1 in bands:
        if y1-y0<30: continue
        res = try_region(card[y0:y1,:], label)
        if res: return res

    # Pass 4 — fine rotations (catches residual tilt from hand-held capture)
    cx,cy = w//2,h//2
    for angle in [-3,3,-5,5,-8,8,-10,10,-12,12,-15,15,-18,18,-20,20]:
        M = cv2.getRotationMatrix2D((cx,cy),angle,1.0)
        rot = cv2.warpAffine(card,M,(w,h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
        res = try_region(rot,f"rot{angle:+d}")
        if res:
            log.info("Decoded at %+d° rotation",angle)
            return res

    # Pass 5 — 90°/270° for portrait-held cards
    for code,label in [(cv2.ROTATE_90_CLOCKWISE,"rot90"),
                       (cv2.ROTATE_90_COUNTERCLOCKWISE,"rot270")]:
        res = try_region(cv2.rotate(card,code),label)
        if res: return res

    return None


# ═══════════════════════════════════════════════════════════════
#  OCR (front)
# ═══════════════════════════════════════════════════════════════
def ocr_front(card: np.ndarray) -> dict:
    if not _HAS_TESSERACT: return {}
    clahe = cv2.createCLAHE(2.0,(8,8))
    gray  = cv2.cvtColor(card,cv2.COLOR_BGR2GRAY)
    enh   = clahe.apply(cv2.resize(gray,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
    text  = pytesseract.image_to_string(enh,config="--psm 6 --oem 3")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: dict[str,str] = {}
    for line in lines:
        if re.match(r"^[A-Z]{2}$",line) and "ocr_state" not in out: out["ocr_state"]=line
        m=re.search(r"\b([A-Z]\d{7,8}|\d{7,9})\b",line)
        if m and "ocr_license_number" not in out: out["ocr_license_number"]=m.group(1)
        m=re.search(r"\b(\d{2}/\d{2}/\d{4})\b",line)
        if m and "ocr_dob" not in out: out["ocr_dob"]=m.group(1)
        m=re.search(r"EXP[:\s]*(\d{2}/\d{2}/\d{4})",line,re.I)
        if m: out["ocr_expiry"]=m.group(1)
    return out


# ═══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════
@app.get("/",tags=["Health"])
def root():
    return {"api":"DL Scanner v3.2","zxingcpp":_HAS_ZXING,
            "pyzbar":True,"pdf417":_HAS_PDF417,"ocr":_HAS_TESSERACT,
            "ts":datetime.utcnow().isoformat()}

@app.get("/health",tags=["Health"])
def health():
    return {"status":"ok","ts":datetime.utcnow().isoformat()}


@app.post("/scan/front",tags=["Scan"])
async def scan_front(file: UploadFile = File(...)):
    """
    Receive guide-cropped 856×540 card image.
    Deskew → OCR → return corrected card + OCR fields.
    """
    raw  = await file.read()
    card = _load(raw)
    card = _ensure_856x540(card)
    log.info("scan/front  %dx%d  %.1fkb", card.shape[1],card.shape[0],len(raw)/1024)

    card       = crop_card(card)
    card,angle = deskew(card)
    ocr        = ocr_front(card)

    return JSONResponse({
        "success":       True,
        "cropped_image": f"data:image/jpeg;base64,{_b64(card)}",
        "ocr_fields":    ocr,
        "deskew_angle":  round(angle,1),
    })


@app.post("/scan/back",tags=["Scan"])
async def scan_back(
    file:             UploadFile = File(...),
    raw_barcode_text: Optional[str] = Form(None),
):
    """
    Receive guide-cropped 856×540 card image.
    
    Decode priority:
      A. ZXing client pre-decoded text (live scan found barcode before capture)
      B. Server: deskew → multi-pass decode with 15 preprocessing variants
                 × 5 pass strategies × up to 16 rotation angles
    """
    raw  = await file.read()
    card = _load(raw)
    card = _ensure_856x540(card)
    log.info("scan/back  %dx%d  %.1fkb  pre=%s",
             card.shape[1],card.shape[0],len(raw)/1024,bool(raw_barcode_text))

    card       = crop_card(card)
    card,angle = deskew(card)
    b64        = _b64(card)

    # Priority A — ZXing already decoded on the client (fastest path)
    if raw_barcode_text and ("ANSI" in raw_barcode_text or "DAQ" in raw_barcode_text):
        parsed = parse_aamva(raw_barcode_text)
        if parsed:
            log.info("back via ZXing client  fields=%d", len(parsed))
            return JSONResponse({
                "success":True,"source":"zxing_client","barcode_type":"PDF417",
                "barcode_image": f"data:image/jpeg;base64,{b64}",
                "parsed_data":parsed,"deskew_angle":round(angle,1),
                "message":"Decoded by ZXing (client-side)",
            })

    # Priority B — server multi-pass decode
    result = decode_barcode(card)

    if result:
        log.info("back via server  type=%s  fields=%d  angle=%.1f°",
                 result["type"],len(result["parsed"]),angle)
        return JSONResponse({
            "success":True,"source":"server","barcode_type":result["type"],
            "barcode_image": f"data:image/jpeg;base64,{b64}",
            "parsed_data":result["parsed"],"deskew_angle":round(angle,1),
            "message":"Decoded server-side",
        })

    log.warning("back: not decoded  angle=%.1f°",angle)
    return JSONResponse({
        "success":False,"source":"none",
        "barcode_image": f"data:image/jpeg;base64,{b64}",
        "parsed_data":{},"deskew_angle":round(angle,1),
        "message":"Barcode not decoded. Try: brighter lighting, hold card flat, avoid glare.",
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app",host="0.0.0.0",port=8000,reload=True)