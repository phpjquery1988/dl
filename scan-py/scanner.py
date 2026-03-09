#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║           USA DRIVER LICENSE SCANNER  —  scanner.py             ║
║   Engine: zxing-cpp (PDF417) + OpenCV (camera)                  ║
║   Parser: AAMVA DL/ID Standard (all US states + Canada)         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import cv2
import zxingcpp
import numpy as np
import argparse
import time
from pathlib import Path
from datetime import datetime

# Local AAMVA parser module
from aamva_parser import AAMVAParser, format_license_table
from ui import UI


# ── Constants ────────────────────────────────────────────────────────────────

APP_NAME    = "USA DL SCANNER"
APP_VERSION = "1.0.0"
WINDOW_NAME = "USA Driver License Scanner  |  Press Q to quit  |  S to save"

# Overlay colours (BGR)
CLR_GREEN  = (0, 220, 80)
CLR_BLUE   = (235, 120, 30)
CLR_RED    = (50,  60, 230)
CLR_WHITE  = (255, 255, 255)
CLR_YELLOW = (0,  210, 245)
CLR_DARK   = (20,  20,  20)

# Scan zone (% of frame)
ZONE_X1, ZONE_Y1 = 0.05, 0.25
ZONE_X2, ZONE_Y2 = 0.95, 0.75

# Minimum barcode confidence  
MIN_CONFIDENCE = 0


# ── Camera scanner ───────────────────────────────────────────────────────────

class LicenseScanner:
    """Real-time PDF417 license scanner using webcam."""

    def __init__(self, camera_index: int = 0, save_dir: str = "scans"):
        self.camera_index = camera_index
        self.save_dir     = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)

        self.cap         = None
        self.last_result = None
        self.scan_count  = 0
        self.frame_count = 0
        self.fps         = 0
        self._fps_time   = time.time()

        self.parser  = AAMVAParser()
        self.ui      = UI()

    # ── Camera setup ──────────────────────────────────────────────────────

    def open_camera(self) -> bool:
        UI.header(APP_NAME, APP_VERSION)
        print(f"  Opening camera #{self.camera_index}…")

        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            UI.error(f"Cannot open camera index {self.camera_index}.")
            return False

        # Prefer HD resolution for better barcode reads
        for w, h in [(1920, 1080), (1280, 720), (640, 480)]:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_w >= w * 0.9:
                break

        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        UI.success(f"Camera opened  →  {actual_w}×{actual_h}")
        print()
        return True

    # ── Frame processing ──────────────────────────────────────────────────

    def _decode_frame(self, frame: np.ndarray):
        """Run zxing-cpp PDF417 decoder on the frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Enhance contrast for harder reads
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        results = zxingcpp.read_barcodes(
            enhanced,
            formats=zxingcpp.BarcodeFormat.PDF417,
        )

        # Filter to valid results only
        valid = [r for r in results if r.valid and r.text]
        return valid

    def _draw_overlay(self, frame: np.ndarray, results, scanning: bool) -> np.ndarray:
        """Draw scan zone, detections, and HUD onto the frame."""
        h, w = frame.shape[:2]
        overlay = frame.copy()

        # ── Semi-transparent scan zone box ───────────────────────────────
        x1 = int(w * ZONE_X1); y1 = int(h * ZONE_Y1)
        x2 = int(w * ZONE_X2); y2 = int(h * ZONE_Y2)

        mask = frame.copy()
        cv2.rectangle(mask, (0, 0),   (w, y1),  CLR_DARK, -1)
        cv2.rectangle(mask, (0, y2),  (w, h),   CLR_DARK, -1)
        cv2.rectangle(mask, (0, y1),  (x1, y2), CLR_DARK, -1)
        cv2.rectangle(mask, (x2, y1),(w, y2),   CLR_DARK, -1)
        frame = cv2.addWeighted(frame, 0.6, mask, 0.4, 0)

        # ── Animated scan corners ─────────────────────────────────────────
        corner_len = 24
        thickness  = 2
        clr = CLR_GREEN if results else CLR_BLUE

        for px, py, dx, dy in [
            (x1, y1, 1, 1), (x2, y1, -1, 1),
            (x1, y2, 1,-1), (x2, y2, -1,-1),
        ]:
            cv2.line(frame, (px, py), (px + dx * corner_len, py), clr, thickness)
            cv2.line(frame, (px, py), (px, py + dy * corner_len), clr, thickness)

        # ── Animated scan line ────────────────────────────────────────────
        if scanning and not results:
            progress = (time.time() % 2.0) / 2.0   # 0→1 over 2 seconds
            scan_y   = y1 + int((y2 - y1) * progress)
            cv2.line(frame, (x1 + 4, scan_y), (x2 - 4, scan_y), CLR_BLUE, 1)
            # Glow effect
            glow = np.zeros_like(frame)
            cv2.line(glow, (x1 + 4, scan_y), (x2 - 4, scan_y), CLR_BLUE, 6)
            frame = cv2.addWeighted(frame, 1.0, glow, 0.3, 0)

        # ── Detected barcode outline ──────────────────────────────────────
        for result in results:
            pts = result.position
            corners = np.array([
                [pts.top_left.x,     pts.top_left.y],
                [pts.top_right.x,    pts.top_right.y],
                [pts.bottom_right.x, pts.bottom_right.y],
                [pts.bottom_left.x,  pts.bottom_left.y],
            ], dtype=np.int32)

            cv2.polylines(frame, [corners], True, CLR_GREEN, 2)

            # Fill with transparent green
            fill = frame.copy()
            cv2.fillPoly(fill, [corners], CLR_GREEN)
            frame = cv2.addWeighted(frame, 0.85, fill, 0.15, 0)

            # Detection label
            cv2.putText(
                frame, "PDF417 DETECTED",
                (pts.top_left.x, pts.top_left.y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, CLR_GREEN, 1, cv2.LINE_AA
            )

        # ── HUD — top bar ─────────────────────────────────────────────────
        cv2.rectangle(frame, (0, 0), (w, 36), (10, 10, 10), -1)
        hud_left  = f"  {APP_NAME}  v{APP_VERSION}"
        hud_right = f"FPS: {self.fps:.1f}  |  Scans: {self.scan_count}"
        cv2.putText(frame, hud_left,  (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, CLR_WHITE, 1, cv2.LINE_AA)
        cv2.putText(frame, hud_right, (w - 220, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160,160,160), 1, cv2.LINE_AA)

        # ── HUD — bottom bar ──────────────────────────────────────────────
        cv2.rectangle(frame, (0, h - 36), (w, h), (10, 10, 10), -1)
        hint = "Align PDF417 barcode on the BACK of a US driver's license within the frame"
        if results:
            hint = "✓ BARCODE DETECTED  —  Reading data…"
            clr_hint = CLR_GREEN
        elif scanning:
            clr_hint = (160, 160, 160)
        else:
            clr_hint = (100, 100, 100)
        cv2.putText(frame, hint, (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, clr_hint, 1, cv2.LINE_AA)

        # ── Zone label ────────────────────────────────────────────────────
        cv2.putText(frame, "SCAN ZONE", (x1 + 8, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, clr, 1, cv2.LINE_AA)

        return frame

    # ── Main scanning loop ────────────────────────────────────────────────

    def run(self):
        """Main camera loop."""
        if not self.open_camera():
            return

        UI.info("Controls:  Q = quit  |  S = save last result  |  R = reset")
        UI.info("Point the back of a US driver's license at the camera.")
        print()

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 960, 640)

        scanning       = True
        freeze_frames  = 0   # frames to hold still after a successful scan
        frozen_frame   = None

        while True:
            ret, frame = self.cap.read()
            if not ret:
                UI.error("Frame capture failed.")
                break

            self.frame_count += 1

            # FPS calculation
            now = time.time()
            if now - self._fps_time >= 1.0:
                self.fps       = self.frame_count / (now - self._fps_time)
                self.frame_count = 0
                self._fps_time = now

            # ── Decode ───────────────────────────────────────────────────
            results = []
            if scanning and freeze_frames == 0:
                results = self._decode_frame(frame)

                if results:
                    raw_text = results[0].text
                    parsed   = self.parser.parse(raw_text)
                    if parsed:
                        self.scan_count += 1
                        self.last_result = parsed
                        self.last_result["_raw"] = raw_text
                        self.last_result["_ts"]  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Print results to terminal
                        print("\n" + format_license_table(parsed))

                        # Freeze display for 2 seconds to show detection box
                        freeze_frames  = 60
                        frozen_frame   = frame.copy()
                        scanning       = False   # pause scanning until reset

            # ── Draw ─────────────────────────────────────────────────────
            if freeze_frames > 0:
                display = self._draw_overlay(frozen_frame.copy(), results if results else [], False)
                freeze_frames -= 1
                if freeze_frames == 0:
                    # Show "press R to scan again" prompt
                    pass
            else:
                display = self._draw_overlay(frame, results, scanning)

            # ── Resume prompt overlay ─────────────────────────────────────
            if not scanning and freeze_frames == 0:
                h, w = display.shape[:2]
                prompt = "Scan complete  |  Press R to scan again  |  S to save  |  Q to quit"
                cv2.rectangle(display, (0, h//2 - 20), (w, h//2 + 20), (0, 0, 0), -1)
                cv2.putText(display, prompt,
                            (w//2 - len(prompt)*4, h//2 + 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, CLR_YELLOW, 1, cv2.LINE_AA)

            cv2.imshow(WINDOW_NAME, display)

            # ── Key handling ─────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('r') or key == ord('R'):
                scanning = True
                freeze_frames = 0
                UI.info("Scanner reset — ready for next scan.")
            elif key == ord('s') or key == ord('S'):
                if self.last_result:
                    self._save_result(self.last_result)
                else:
                    UI.warn("No scan result to save yet.")

        self.cap.release()
        cv2.destroyAllWindows()
        UI.success("Scanner closed.")

    # ── Save result ───────────────────────────────────────────────────────

    def _save_result(self, data: dict):
        """Save last scan result to a JSON file."""
        import json
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = data.get("license_number", "unknown").replace("/", "_")
        path = self.save_dir / f"scan_{name}_{ts}.json"

        # Remove raw bytes from saved output
        save_data = {k: v for k, v in data.items() if not k.startswith("_")}
        with open(path, "w") as f:
            json.dump(save_data, f, indent=2)
        UI.success(f"Saved → {path}")


# ── Image file scanner ───────────────────────────────────────────────────────

class ImageScanner:
    """Decode a driver's license barcode from a static image file."""

    def __init__(self):
        self.parser = AAMVAParser()

    def scan(self, image_path: str) -> bool:
        UI.header(APP_NAME, APP_VERSION)
        path = Path(image_path)

        if not path.exists():
            UI.error(f"File not found: {image_path}")
            return False

        UI.info(f"Loading image: {path.name}")
        img = cv2.imread(str(path))
        if img is None:
            UI.error("Cannot read image. Ensure it is a valid JPG/PNG/BMP/TIFF.")
            return False

        h, w = img.shape[:2]
        UI.info(f"Image size: {w}×{h}")
        print()

        # Preprocessing pipeline for improved read rate
        attempts = self._preprocessing_pipeline(img)
        
        for label, processed in attempts:
            print(f"  Trying: {label}…", end=" ", flush=True)
            results = zxingcpp.read_barcodes(
                processed,
                formats=zxingcpp.BarcodeFormat.PDF417,
            )
            valid = [r for r in results if r.valid and r.text]

            if valid:
                print("✓ FOUND")
                raw = valid[0].text
                parsed = self.parser.parse(raw)
                if parsed:
                    print("\n" + format_license_table(parsed))
                    return True
                else:
                    UI.warn("Barcode found but data did not match AAMVA format.")
                    print(f"\nRaw barcode text:\n{raw[:500]}\n")
                    return False
            else:
                print("—")

        UI.error("No PDF417 barcode detected after all preprocessing attempts.")
        UI.info("Tips for better results:")
        print("   • Photograph the BACK of the license (barcode side)")
        print("   • Ensure good lighting — avoid glare and shadows")
        print("   • Keep the image in focus and barcode filling most of the frame")
        print("   • Try resizing to at least 1200px wide")
        return False

    def _preprocessing_pipeline(self, img: np.ndarray) -> list:
        """Generate a sequence of preprocessed versions to maximise read success."""
        h, w = img.shape[:2]
        attempts = []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Original colour
        attempts.append(("Original colour", img))

        # 2. Grayscale
        attempts.append(("Grayscale", gray))

        # 3. CLAHE enhanced
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        attempts.append(("CLAHE enhanced", enhanced))

        # 4. Upscaled 2× (helps with small barcodes)
        if w < 1600:
            up = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
            up_gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
            attempts.append(("Upscaled 2×", up_gray))

        # 5. Sharpened
        kernel  = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
        sharpen = cv2.filter2D(gray, -1, kernel)
        attempts.append(("Sharpened", sharpen))

        # 6. Adaptive threshold
        thresh = cv2.adaptiveThreshold(
            enhanced, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        attempts.append(("Adaptive threshold", thresh))

        # 7. Deskewed (correct slight rotations)
        deskewed = self._deskew(gray)
        if deskewed is not None:
            attempts.append(("Deskewed", deskewed))

        return attempts

    def _deskew(self, gray: np.ndarray):
        """Detect and correct slight image rotation."""
        try:
            edges  = cv2.Canny(gray, 50, 150)
            lines  = cv2.HoughLinesP(edges, 1, np.pi/180, 80, minLineLength=100, maxLineGap=10)
            if lines is None:
                return None
            angles = []
            for l in lines:
                x1, y1, x2, y2 = l[0]
                if x2 != x1:
                    angles.append(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if not angles:
                return None
            median_angle = np.median(angles)
            if abs(median_angle) < 0.5 or abs(median_angle) > 30:
                return None
            h, w = gray.shape
            M    = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1.0)
            return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        except Exception:
            return None


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="USA Driver License PDF417 Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scanner.py                    # Live camera scan (default camera)
  python scanner.py --camera 1         # Use camera index 1
  python scanner.py --image back.jpg   # Scan from image file
  python scanner.py --list-cameras     # List available cameras
        """
    )
    parser.add_argument("--camera", type=int, default=0,
                        help="Camera device index (default: 0)")
    parser.add_argument("--image", type=str, default=None,
                        help="Path to a license image to scan instead of camera")
    parser.add_argument("--save-dir", type=str, default="scans",
                        help="Directory to save scan results (default: ./scans)")
    parser.add_argument("--list-cameras", action="store_true",
                        help="List available camera devices and exit")
    args = parser.parse_args()

    if args.list_cameras:
        _list_cameras()
        return

    if args.image:
        scanner = ImageScanner()
        ok = scanner.scan(args.image)
        sys.exit(0 if ok else 1)
    else:
        scanner = LicenseScanner(camera_index=args.camera, save_dir=args.save_dir)
        scanner.run()


def _list_cameras():
    """Print all available camera indices."""
    UI.header(APP_NAME, APP_VERSION)
    print("  Scanning for cameras…\n")
    found = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            found.append((i, w, h))
            cap.release()

    if not found:
        UI.warn("No cameras detected.")
    else:
        for idx, w, h in found:
            mark = " ◀ default" if idx == 0 else ""
            UI.success(f"  Camera {idx}:  {w}×{h}{mark}")
    print()


if __name__ == "__main__":
    main()
