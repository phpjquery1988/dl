"""
aamva_parser.py  —  AAMVA DL/ID Standard Parser
================================================
Parses the raw ASCII data encoded in the PDF417 barcode on the back of
US & Canadian driver's licenses, following AAMVA standard DL/ID-2000
through AAMVA 2020 (card version 1–10).

Reference: AAMVA DL/ID Card Design Standard (2020)
"""

from __future__ import annotations
import re
from datetime import datetime, date
from typing import Optional


# ── AAMVA Field Definitions ───────────────────────────────────────────────────

AAMVA_FIELDS: dict[str, dict] = {
    # ── Mandatory subfile fields ──────────────────────────────────────────
    "DCA": {"name": "vehicle_class",        "label": "Vehicle Class"},
    "DCB": {"name": "restrictions",         "label": "Restrictions"},
    "DCD": {"name": "endorsements",         "label": "Endorsements"},
    "DBA": {"name": "expiry_date",          "label": "Expiry Date",         "type": "date"},
    "DCS": {"name": "last_name",            "label": "Last Name"},
    "DAC": {"name": "first_name",           "label": "First Name"},
    "DAD": {"name": "middle_name",          "label": "Middle Name"},
    "DBD": {"name": "issue_date",           "label": "Issue Date",          "type": "date"},
    "DBB": {"name": "date_of_birth",        "label": "Date of Birth",       "type": "date"},
    "DBC": {"name": "sex",                  "label": "Sex",                 "type": "sex"},
    "DAY": {"name": "eye_color",            "label": "Eye Color"},
    "DAU": {"name": "height",               "label": "Height",              "type": "height"},
    "DAG": {"name": "address_street",       "label": "Address"},
    "DAI": {"name": "address_city",         "label": "City"},
    "DAJ": {"name": "address_state",        "label": "State"},
    "DAK": {"name": "address_zip",          "label": "ZIP Code",            "type": "zip"},
    "DAQ": {"name": "license_number",       "label": "License Number"},
    "DCF": {"name": "document_id",          "label": "Document ID"},
    "DCG": {"name": "country",              "label": "Country"},
    "DAA": {"name": "full_name_field",      "label": "Full Name (raw)"},
    # ── Optional fields ───────────────────────────────────────────────────
    "DAH": {"name": "address_street_2",     "label": "Address Line 2"},
    "DAZ": {"name": "hair_color",           "label": "Hair Color"},
    "DAW": {"name": "weight_lbs",           "label": "Weight (lbs)",        "type": "weight"},
    "DAX": {"name": "weight_kg",            "label": "Weight (kg)"},
    "DCI": {"name": "place_of_birth",       "label": "Place of Birth"},
    "DCJ": {"name": "audit_info",           "label": "Audit Information"},
    "DCK": {"name": "inventory_control",    "label": "Inventory Control #"},
    "DBN": {"name": "alias_family_name",    "label": "Alias / AKA Family Name"},
    "DBG": {"name": "alias_given_name",     "label": "Alias / AKA Given Name"},
    "DBS": {"name": "alias_suffix",         "label": "Alias / AKA Suffix Name"},
    "DCU": {"name": "name_suffix",          "label": "Name Suffix"},
    "DCE": {"name": "weight_range",         "label": "Weight Range"},
    "DCL": {"name": "race_ethnicity",       "label": "Race / Ethnicity"},
    "DCM": {"name": "std_vehicle_class",    "label": "Standard Vehicle Class"},
    "DCN": {"name": "std_endorsements",     "label": "Standard Endorsement Code"},
    "DCO": {"name": "std_restrictions",     "label": "Standard Restriction Code"},
    "DCP": {"name": "jurisdiction_class",   "label": "Jurisdiction-Specific Class"},
    "DCQ": {"name": "jurisdiction_restrict","label": "Jurisdiction-Specific Restrictions"},
    "DCR": {"name": "jurisdiction_endorse", "label": "Jurisdiction-Specific Endorsements"},
    "DDA": {"name": "compliance_type",      "label": "Compliance Type"},
    "DDB": {"name": "card_revision_date",   "label": "Card Revision Date",  "type": "date"},
    "DDC": {"name": "hazmat_expiry",        "label": "HazMat Expiry Date",  "type": "date"},
    "DDD": {"name": "limited_duration",     "label": "Limited Duration Doc Indicator"},
    "DAE": {"name": "name_prefix",          "label": "Name Prefix"},
    "DDH": {"name": "under_18_until",       "label": "Under 18 Until",      "type": "date"},
    "DDI": {"name": "under_19_until",       "label": "Under 19 Until",      "type": "date"},
    "DDJ": {"name": "under_21_until",       "label": "Under 21 Until",      "type": "date"},
    "DDK": {"name": "organ_donor",          "label": "Organ Donor"},
    "DDL": {"name": "veteran",              "label": "Veteran"},
}

# Field type formatters
EYE_COLOR_MAP = {
    "BLK": "Black", "BLU": "Blue", "BRO": "Brown", "GRY": "Gray",
    "GRN": "Green", "HAZ": "Hazel", "MAR": "Maroon", "PNK": "Pink",
    "DIC": "Dichromatic", "UNK": "Unknown",
}

HAIR_COLOR_MAP = {
    "BAL": "Bald", "BLK": "Black", "BLN": "Blond", "BRO": "Brown",
    "GRY": "Gray", "RED": "Red", "SDY": "Sandy", "WHI": "White", "UNK": "Unknown",
}

SEX_MAP = {"1": "Male", "2": "Female", "9": "Not Specified",
           "M": "Male", "F": "Female", "X": "Non-binary / Not Specified"}

STATE_MAP = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "AS": "American Samoa", "GU": "Guam", "PR": "Puerto Rico", "VI": "U.S. Virgin Islands",
    # Canadian provinces
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "ON": "Ontario",
    "PE": "Prince Edward Island", "QC": "Quebec", "SK": "Saskatchewan",
}


# ── Parser class ─────────────────────────────────────────────────────────────

class AAMVAParser:
    """
    Parses AAMVA-compliant PDF417 barcode data from US/Canada driver's licenses.
    """

    def parse(self, raw: str) -> Optional[dict]:
        """
        Parse raw barcode text into a structured dictionary.
        Returns None if the text doesn't look like AAMVA data.
        """
        if not raw or len(raw) < 20:
            return None

        # ── Detect AAMVA header ───────────────────────────────────────────
        # AAMVA barcodes start with @\n\x1e\rANSI  (or similar)
        # Some versions start with @\nIIN or just with field codes
        is_aamva = (
            "@" in raw[:10]
            or "ANSI " in raw[:30]
            or "AAMVA" in raw[:30]
            or re.search(r'D[A-Z]{2}', raw) is not None
        )

        if not is_aamva:
            return None

        # ── Extract header metadata ───────────────────────────────────────
        card_version = self._extract_card_version(raw)
        issuer_id    = self._extract_issuer_id(raw)

        # ── Extract all field values ──────────────────────────────────────
        fields = self._extract_fields(raw)
        if not fields:
            return None

        # ── Build structured output ───────────────────────────────────────
        data: dict = {
            "_card_version": card_version,
            "_issuer_id":    issuer_id,
        }

        for code, field_def in AAMVA_FIELDS.items():
            raw_val = fields.get(code)
            if raw_val:
                name     = field_def["name"]
                fmt_type = field_def.get("type")
                data[name] = self._format_value(raw_val, fmt_type)

        # ── Derived / computed fields ─────────────────────────────────────
        data["full_name"]   = self._build_full_name(data, fields)
        data["age"]         = self._calc_age(data.get("date_of_birth"))
        data["is_expired"]  = self._is_expired(data.get("expiry_date"))
        data["is_21_plus"]  = self._is_21_plus(data.get("date_of_birth"))
        data["is_18_plus"]  = self._is_18_plus(data.get("date_of_birth"))
        data["state_full"]  = STATE_MAP.get(data.get("address_state", ""), data.get("address_state", ""))

        # Eye / hair color human-readable
        if "eye_color" in data:
            data["eye_color"] = EYE_COLOR_MAP.get(data["eye_color"].upper(), data["eye_color"])
        if "hair_color" in data:
            data["hair_color"] = HAIR_COLOR_MAP.get(data["hair_color"].upper(), data["hair_color"])

        return data

    # ── Field extraction ──────────────────────────────────────────────────

    def _extract_fields(self, raw: str) -> dict[str, str]:
        """Extract all 3-char field codes and their values from the raw string."""
        fields: dict[str, str] = {}

        # Split on common AAMVA delimiters
        lines = re.split(r'[\r\n\x1c\x1d\x1e]', raw)

        for line in lines:
            line = line.strip()
            if len(line) >= 4:
                code = line[:3]
                val  = line[3:].strip()
                # Only store recognised field codes
                if re.match(r'^D[A-Z]{2}$', code) and val:
                    fields[code] = val

        # Fallback: inline scan (some cards use no line breaks between fields)
        if len(fields) < 3:
            for match in re.finditer(r'(D[A-Z]{2})([^\r\n]{1,100}?)(?=D[A-Z]{2}|$)', raw):
                code = match.group(1)
                val  = match.group(2).strip()
                if val and code not in fields:
                    fields[code] = val

        return fields

    def _extract_card_version(self, raw: str) -> Optional[str]:
        m = re.search(r'ANSI\s+\d{6}(\d{2})', raw)
        if m:
            return m.group(1)
        m = re.search(r'@\s*\n\x1e\rANSI\s+\d{6}(\d{2})', raw)
        if m:
            return m.group(1)
        return None

    def _extract_issuer_id(self, raw: str) -> Optional[str]:
        m = re.search(r'ANSI\s+(\d{6})', raw)
        return m.group(1) if m else None

    # ── Value formatters ──────────────────────────────────────────────────

    def _format_value(self, val: str, fmt_type: Optional[str]) -> str:
        val = val.strip()
        if not val or val.upper() in ("NONE", "N/A", "NA", "NON", ""):
            return ""

        if fmt_type == "date":
            return self._fmt_date(val)
        elif fmt_type == "sex":
            return SEX_MAP.get(val, val)
        elif fmt_type == "height":
            return self._fmt_height(val)
        elif fmt_type == "zip":
            return self._fmt_zip(val)
        elif fmt_type == "weight":
            return self._fmt_weight(val)
        return val

    def _fmt_date(self, val: str) -> str:
        """
        AAMVA dates: MMDDYYYY (most states) or YYYYMMDD (some states)
        Returns MM/DD/YYYY formatted string.
        """
        val = re.sub(r'[^0-9]', '', val)
        if len(val) == 8:
            # Heuristic: if first 4 digits look like a year (> 1900)
            first4 = int(val[:4])
            if 1900 < first4 < 2100:
                # YYYYMMDD format
                return f"{val[4:6]}/{val[6:8]}/{val[:4]}"
            else:
                # MMDDYYYY format
                return f"{val[:2]}/{val[2:4]}/{val[4:]}"
        return val

    def _fmt_height(self, val: str) -> str:
        """
        AAMVA heights: '509' = 5'09"  or  '175 cm' / '175CM'
        """
        val = val.strip()
        # Metric: e.g. "175 cm"
        m = re.match(r'^(\d+)\s*cm$', val, re.IGNORECASE)
        if m:
            cm = int(m.group(1))
            total_in = cm / 2.54
            ft = int(total_in // 12)
            inch = int(round(total_in % 12))
            return f"{ft}'{inch:02d}\"  ({cm} cm)"

        # Imperial: e.g. "509" = 5'9"
        digits = re.sub(r'[^0-9]', '', val)
        if len(digits) == 3:
            ft   = digits[0]
            inch = digits[1:]
            return f"{ft}'{inch}\""

        # "5 ft 9 in" format
        m = re.match(r'(\d)\s*ft?\s*(\d{1,2})', val, re.IGNORECASE)
        if m:
            return f"{m.group(1)}'{int(m.group(2)):02d}\""

        return val

    def _fmt_zip(self, val: str) -> str:
        digits = re.sub(r'[^0-9]', '', val)
        if len(digits) == 9:
            return f"{digits[:5]}-{digits[5:]}"
        return digits[:5] if len(digits) >= 5 else val

    def _fmt_weight(self, val: str) -> str:
        digits = re.sub(r'[^0-9]', '', val)
        if digits:
            return f"{int(digits)} lbs"
        return val

    # ── Name building ─────────────────────────────────────────────────────

    def _build_full_name(self, data: dict, raw_fields: dict) -> str:
        """
        Construct a human-readable full name from whichever name fields exist.
        AAMVA full name format: LAST,FIRST,MIDDLE  or  LAST,FIRST MIDDLE
        """
        # Try DAA (full name composite field)
        daa = raw_fields.get("DAA", "").strip()
        if daa:
            if "," in daa:
                parts = [p.strip() for p in daa.split(",")]
                # parts[0]=last, parts[1]=first, parts[2]=middle/suffix
                name_parts = []
                if len(parts) > 1 and parts[1]: name_parts.append(parts[1].title())
                if len(parts) > 2 and parts[2]: name_parts.append(parts[2].title())
                if parts[0]:                    name_parts.append(parts[0].title())
                if name_parts:
                    return " ".join(name_parts)

        # Build from components
        first  = data.get("first_name", "").strip().title()
        middle = data.get("middle_name", "").strip().title()
        last   = data.get("last_name",  "").strip().title()

        parts = [p for p in [first, middle, last] if p]
        if parts:
            return " ".join(parts)

        return ""

    # ── Age / expiry helpers ──────────────────────────────────────────────

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse formatted date string (MM/DD/YYYY) into a date object."""
        if not date_str:
            return None
        m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                return None
        return None

    def _calc_age(self, dob_str: str) -> Optional[int]:
        d = self._parse_date(dob_str)
        if not d:
            return None
        today = date.today()
        age   = today.year - d.year
        if (today.month, today.day) < (d.month, d.day):
            age -= 1
        return age

    def _is_expired(self, exp_str: str) -> Optional[bool]:
        d = self._parse_date(exp_str)
        if not d:
            return None
        return d < date.today()

    def _is_21_plus(self, dob_str: str) -> Optional[bool]:
        age = self._calc_age(dob_str)
        return age >= 21 if age is not None else None

    def _is_18_plus(self, dob_str: str) -> Optional[bool]:
        age = self._calc_age(dob_str)
        return age >= 18 if age is not None else None


# ── Terminal table formatter ──────────────────────────────────────────────────

def format_license_table(data: dict) -> str:
    """Return a formatted terminal table of parsed license data."""
    lines = []

    # Box drawing
    W = 62
    TL, TR, BL, BR = "╔", "╗", "╚", "╝"
    H, V           = "═", "║"
    ML, MR, MC     = "╠", "╣", "═"

    def hline(left, fill, right):
        return left + fill * (W - 2) + right

    def row(label, value, width=W):
        if not value:
            return None
        label_str = f" {label:<18}"
        max_val   = width - len(label_str) - 4
        value_str = str(value)[:max_val]
        pad       = width - len(label_str) - len(value_str) - 2
        return f"{V}{label_str}{value_str}{' ' * max(pad, 0)}{V}"

    # ── Header ────────────────────────────────────────────────────────────
    lines.append(hline(TL, H, TR))
    title = "  🪪  USA DRIVER LICENSE  —  SCAN RESULT"
    lines.append(f"{V}{title:<{W-2}}{V}")
    lines.append(hline(ML, MC, MR))

    # ── Name & state ──────────────────────────────────────────────────────
    name      = data.get("full_name", "")
    state     = data.get("address_state", "")
    state_full= data.get("state_full", state)
    age       = data.get("age")

    if name:
        lines.append(row("Full Name", name.upper()))
    if state_full:
        lines.append(row("Issuing State", f"{state_full} ({state})" if state != state_full else state))

    lines.append(hline(ML, MC, MR))

    # ── Identity fields ────────────────────────────────────────────────────
    identity_fields = [
        ("License Number",  data.get("license_number")),
        ("Date of Birth",   data.get("date_of_birth") + (f"  (Age {age})" if age else "")),
        ("Sex",             data.get("sex")),
        ("Eye Color",       data.get("eye_color")),
        ("Hair Color",      data.get("hair_color")),
        ("Height",          data.get("height")),
        ("Weight",          data.get("weight_lbs")),
    ]
    for label, val in identity_fields:
        r = row(label, val)
        if r:
            lines.append(r)

    lines.append(hline(ML, MC, MR))

    # ── License details ────────────────────────────────────────────────────
    expired    = data.get("is_expired")
    exp_str    = data.get("expiry_date", "")
    exp_tag    = " ⚠ EXPIRED" if expired else " ✓ VALID" if expired is False else ""
    
    license_fields = [
        ("Issue Date",      data.get("issue_date")),
        ("Expiry Date",     (exp_str + exp_tag) if exp_str else None),
        ("Vehicle Class",   data.get("vehicle_class")),
        ("Restrictions",    data.get("restrictions")),
        ("Endorsements",    data.get("endorsements")),
        ("Document ID",     data.get("document_id")),
    ]
    for label, val in license_fields:
        r = row(label, val)
        if r:
            lines.append(r)

    lines.append(hline(ML, MC, MR))

    # ── Address ────────────────────────────────────────────────────────────
    addr_fields = [
        ("Street",          data.get("address_street")),
        ("Address Line 2",  data.get("address_street_2")),
        ("City",            data.get("address_city")),
        ("ZIP Code",        data.get("address_zip")),
        ("Country",         data.get("country")),
    ]
    for label, val in addr_fields:
        r = row(label, val)
        if r:
            lines.append(r)

    lines.append(hline(ML, MC, MR))

    # ── Status indicators ──────────────────────────────────────────────────
    def indicator(label, value):
        if value is None:
            return row(label, "—")
        icon = "✓  YES" if value else "✗  NO"
        return row(label, icon)

    lines.append(indicator("21+ (Legal Age)",  data.get("is_21_plus")))
    lines.append(indicator("18+ ",             data.get("is_18_plus")))
    lines.append(indicator("Organ Donor",      data.get("organ_donor") in ("1", "Y", "Yes")
                           if data.get("organ_donor") else None))
    lines.append(indicator("Veteran",          data.get("veteran") in ("1", "Y", "Yes")
                           if data.get("veteran") else None))

    # ── Footer ─────────────────────────────────────────────────────────────
    lines.append(hline(BL, H, BR))

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"  Scanned: {ts}  |  AAMVA Card v{data.get('_card_version', '?')}")

    return "\n".join(l for l in lines if l is not None)
