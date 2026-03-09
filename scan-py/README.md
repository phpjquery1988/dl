# 🪪 USA Driver License Scanner

Real-time PDF417 barcode scanner for US driver's licenses, written in Python.  
Decodes all AAMVA-standard fields and displays them in a clean terminal table.

---

## Engine

| Component | Library | Why |
|-----------|---------|-----|
| PDF417 decoder | **zxing-cpp** | Best open-source PDF417 accuracy; pure C++ speed |
| Camera capture | **OpenCV** | Industry-standard; works on Windows / macOS / Linux |
| AAMVA parser | Built-in | Full AAMVA DL/ID 2020 field mapping |

> **Why not Cognex?**  
> Cognex Mobile Barcode SDK was officially discontinued on **September 30, 2025**.  
> `zxing-cpp` is the highest-accuracy free alternative for PDF417 in Python.

---

## Install

```bash
cd dlscanner
pip install -r requirements.txt
```

### System dependencies (macOS / Linux)

```bash
# macOS (Homebrew)
brew install zbar

# Ubuntu / Debian
sudo apt-get install libzbar0 libzbar-dev
```

No extra setup needed on Windows — wheels include everything.

---

## Usage

### 🎥 Live camera scan (default)

```bash
python scanner.py
```

Point the **back** of a US driver's license (the side with the PDF417 barcode) at the camera.

### 📷 Scan from an image file

```bash
python scanner.py --image /path/to/license_back.jpg
```

### 🔢 Use a different camera

```bash
python scanner.py --camera 1       # use camera index 1
python scanner.py --list-cameras   # list all available cameras
```

### 💾 Save results

```bash
python scanner.py --save-dir ./results
```

Results are saved as JSON files in the specified directory.

---

## Camera controls

| Key | Action |
|-----|--------|
| `Q` / `Esc` | Quit |
| `R` | Reset — scan another license |
| `S` | Save last result to JSON |

---

## Output example

```
╔══════════════════════════════════════════════════════════════╗
║  🪪  USA DRIVER LICENSE  —  SCAN RESULT                     ║
╠══════════════════════════════════════════════════════════════╣
║ Full Name          JOHN MICHAEL SMITH                        ║
║ Issuing State      California (CA)                           ║
╠══════════════════════════════════════════════════════════════╣
║ License Number     D1234567                                  ║
║ Date of Birth      01/15/1990  (Age 35)                      ║
║ Sex                Male                                      ║
║ Eye Color          Brown                                     ║
║ Hair Color         Black                                     ║
║ Height             5'10"                                     ║
╠══════════════════════════════════════════════════════════════╣
║ Issue Date         08/20/2022                                ║
║ Expiry Date        01/15/2027  ✓ VALID                       ║
║ Vehicle Class      C                                         ║
╠══════════════════════════════════════════════════════════════╣
║ Street             123 MAIN STREET                           ║
║ City               SACRAMENTO                                ║
║ ZIP Code           95814                                     ║
╠══════════════════════════════════════════════════════════════╣
║ 21+ (Legal Age)    ✓  YES                                    ║
║ 18+                ✓  YES                                    ║
╚══════════════════════════════════════════════════════════════╝
  Scanned: 2026-03-01 14:22:07  |  AAMVA Card v08
```

---

## Supported fields (AAMVA DL/ID 2020)

Full Name · License Number · Date of Birth · Age · Sex · Eye Color · Hair Color · Height · Weight  
Issue Date · Expiry Date · Vehicle Class · Restrictions · Endorsements · Document ID  
Address · City · State · ZIP · Country  
Status: 21+ check · 18+ check · Organ Donor · Veteran · Expired flag

---

## Tips for best scan results

- **Use the back of the license** — the barcode is always on the rear
- Good, even lighting — avoid glare and shadows on the barcode
- Keep the camera steady and close enough that the barcode fills the scan zone
- For image scans, use at least **1200px wide** images in focus
- Rear-facing cameras (phone) work better than front-facing webcams

---

## File structure

```
dlscanner/
├── scanner.py       # Main app — camera loop + image scan mode
├── aamva_parser.py  # AAMVA DL/ID field parser (all 50 states + Canada)
├── ui.py            # Terminal colour output helpers
├── requirements.txt # Python dependencies
└── README.md
```
