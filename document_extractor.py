import io
import os
import re
import shutil
from pathlib import Path
from datetime import date


# ============================================================
# CONFIGURATION
# ============================================================

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

MAX_SINGLE_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_COUNT = 3


# ============================================================
# CUSTOM ERROR
# ============================================================

class DocumentExtractionError(Exception):
    pass


# ============================================================
# GENERAL HELPERS
# ============================================================

def _clean_identifier(value):
    return "".join(
        character
        for character in str(value or "").upper()
        if character.isalnum()
    )


def _normalise_whitespace(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _normalise_lines(text):
    lines = []

    for raw_line in str(text or "").splitlines():

        line = _normalise_whitespace(
            raw_line
        )

        if line:
            lines.append(line)

    return lines


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

def _configure_tesseract(pytesseract):

    possible_paths = []

    env_path = os.environ.get(
        "TESSERACT_CMD",
        "",
    ).strip()

    if env_path:
        possible_paths.append(
            env_path
        )

    system_path = shutil.which(
        "tesseract"
    )

    if system_path:
        possible_paths.append(
            system_path
        )

    possible_paths.extend(
        [
            (
                r"C:\Program Files"
                r"\Tesseract-OCR"
                r"\tesseract.exe"
            ),
            (
                r"C:\Program Files (x86)"
                r"\Tesseract-OCR"
                r"\tesseract.exe"
            ),
        ]
    )

    for path in possible_paths:

        if (
            path
            and Path(path).exists()
        ):

            pytesseract.pytesseract.tesseract_cmd = (
                path
            )

            return path

    raise DocumentExtractionError(
        "Tesseract OCR was not found. "
        "Install Tesseract OCR on Windows or add "
        "TESSERACT_CMD to your .env file."
    )


# ============================================================
# PDF EXTRACTION
# ============================================================

def _extract_text_from_pdf(
    file_bytes,
):

    try:
        import pdfplumber

    except ImportError as exc:

        raise DocumentExtractionError(
            "pdfplumber is not installed. "
            "Run: py -m pip install pdfplumber"
        ) from exc

    extracted_pages = []

    try:

        with pdfplumber.open(
            io.BytesIO(
                file_bytes
            )
        ) as pdf:

            for page in pdf.pages:

                page_text = (
                    page.extract_text()
                    or ""
                )

                if page_text.strip():

                    extracted_pages.append(
                        page_text
                    )

    except Exception as exc:

        raise DocumentExtractionError(
            "Unable to read this PDF."
        ) from exc

    text = "\n".join(
        extracted_pages
    ).strip()

    if not text:

        raise DocumentExtractionError(
            "This PDF does not contain readable text. "
            "If it is a scanned document, upload it "
            "as JPG or PNG."
        )

    return text


# ============================================================
# IMAGE PREPARATION
# ============================================================

def _prepare_image_for_ocr(
    image,
):

    from PIL import (
        ImageOps,
        ImageEnhance,
        ImageFilter,
    )

    image = ImageOps.exif_transpose(
        image
    )

    max_side = 3000

    if max(image.size) > max_side:

        ratio = (
            max_side
            / max(image.size)
        )

        image = image.resize(
            (
                max(
                    1,
                    int(
                        image.width
                        * ratio
                    ),
                ),
                max(
                    1,
                    int(
                        image.height
                        * ratio
                    ),
                ),
            )
        )

    image = ImageOps.grayscale(
        image
    )

    image = ImageOps.autocontrast(
        image
    )

    image = ImageEnhance.Contrast(
        image
    ).enhance(
        1.7
    )

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image


# ============================================================
# IMAGE OCR
# ============================================================

def _extract_text_from_image(
    file_bytes,
):

    try:
        from PIL import Image

    except ImportError as exc:

        raise DocumentExtractionError(
            "Pillow is not installed. "
            "Run: py -m pip install Pillow"
        ) from exc

    try:
        import pytesseract

    except ImportError as exc:

        raise DocumentExtractionError(
            "pytesseract is not installed. "
            "Run: py -m pip install pytesseract"
        ) from exc

    _configure_tesseract(
        pytesseract
    )

    try:

        image = Image.open(
            io.BytesIO(
                file_bytes
            )
        )

        processed_image = (
            _prepare_image_for_ocr(
                image
            )
        )

        text = (
            pytesseract.image_to_string(
                processed_image,
                config="--psm 6",
            )
        )

    except Exception as exc:

        raise DocumentExtractionError(
            "Unable to read the uploaded image."
        ) from exc

    if not text.strip():

        raise DocumentExtractionError(
            "No readable text was detected. "
            "Upload a clearer image."
        )

    return text


# ============================================================
# DOCUMENT TYPE DETECTION
# ============================================================

def _detect_document_type(
    text,
):

    text_upper = str(
        text or ""
    ).upper()

    if any(
        item in text_upper
        for item in (
            "POLLUTION UNDER CONTROL",
            "PUC CERTIFICATE",
            "POLLUTION CONTROL",
            "PUCC",
        )
    ):

        return "PUC"

    if any(
        item in text_upper
        for item in (
            "CERTIFICATE OF INSURANCE",
            "INSURANCE POLICY",
            "POLICY NUMBER",
            "POLICY NO",
        )
    ):

        return "INSURANCE"

    if any(
        item in text_upper
        for item in (
            "REGISTRATION CERTIFICATE",
            "REGISTRATION NO",
            "REGN NO",
            "CHASSIS NO",
            "ENGINE NO",
        )
    ):

        return "RC"

    return "VEHICLE DOCUMENT"


# ============================================================
# LABEL HELPERS
# ============================================================

def _looks_like_label(
    line,
):

    upper = str(
        line or ""
    ).upper()

    labels = (
        "REGISTRATION",
        "REGN",
        "VEHICLE NO",
        "MAKE",
        "MAKER",
        "MODEL",
        "FUEL",
        "CLASS",
        "BODY TYPE",
        "INSURANCE",
        "POLICY",
        "PUC",
        "PUCC",
        "POLLUTION",
        "VALID",
        "EXPIRY",
        "PREMIUM",
        "MANUFACTUR",
        "MFG",
        "VARIANT",
        "TRANSMISSION",
    )

    return any(
        upper.startswith(
            label
        )
        for label in labels
    )


def _value_after_labels(
    text,
    labels,
    max_length=120,
):

    lines = _normalise_lines(
        text
    )

    patterns = [
        re.compile(
            label,
            flags=re.IGNORECASE,
        )
        for label in labels
    ]

    for index, line in enumerate(
        lines
    ):

        for pattern in patterns:

            match = pattern.search(
                line
            )

            if not match:
                continue

            value = line[
                match.end():
            ].strip(
                " :-|#"
            )

            if value:

                return value[
                    :max_length
                ].strip()

            for next_index in range(
                index + 1,
                min(
                    index + 3,
                    len(lines),
                ),
            ):

                next_line = lines[
                    next_index
                ].strip()

                if not next_line:
                    continue

                if _looks_like_label(
                    next_line
                ):
                    break

                return next_line[
                    :max_length
                ].strip()

    return ""


# ============================================================
# DATE EXTRACTION
# ============================================================

def _extract_date(
    value,
):

    raw = str(
        value or ""
    )

    if not raw:
        return ""

    patterns = [
        (
            r"\b(\d{4})[-/.]"
            r"(\d{1,2})[-/.]"
            r"(\d{1,2})\b"
        ),
        (
            r"\b(\d{1,2})[-/.]"
            r"(\d{1,2})[-/.]"
            r"(\d{4})\b"
        ),
    ]

    for index, pattern in enumerate(
        patterns
    ):

        match = re.search(
            pattern,
            raw,
        )

        if not match:
            continue

        try:

            if index == 0:

                year = int(
                    match.group(1)
                )

                month = int(
                    match.group(2)
                )

                day = int(
                    match.group(3)
                )

            else:

                day = int(
                    match.group(1)
                )

                month = int(
                    match.group(2)
                )

                year = int(
                    match.group(3)
                )

            return date(
                year,
                month,
                day,
            ).isoformat()

        except ValueError:
            continue

    return ""


# ============================================================
# YEAR EXTRACTION
# ============================================================

def _extract_year(
    value,
):

    match = re.search(
        r"\b(?:19|20)\d{2}\b",
        str(
            value or ""
        ),
    )

    if not match:
        return ""

    return int(
        match.group(0)
    )


# ============================================================
# REGISTRATION NUMBER
# ============================================================

def _extract_registration_number(
    text,
):

    labelled_value = (
        _value_after_labels(
            text,
            (
                (
                    r"\bREGISTRATION\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
                (
                    r"\bREGN\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
                (
                    r"\bVEHICLE\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
            ),
            max_length=40,
        )
    )

    sources = []

    if labelled_value:
        sources.append(
            labelled_value
        )

    sources.append(
        text
    )

    plate_patterns = [
        (
            r"\b\d{2}\s*BH\s*"
            r"\d{4}\s*[A-Z]{1,2}\b"
        ),
        (
            r"\b[A-Z]{2}\s*"
            r"\d{1,2}\s*"
            r"[A-Z]{1,3}\s*"
            r"\d{1,4}\b"
        ),
    ]

    for source in sources:

        source = str(
            source
        ).upper()

        for pattern in plate_patterns:

            match = re.search(
                pattern,
                source,
            )

            if match:

                value = (
                    _clean_identifier(
                        match.group(0)
                    )
                )

                if (
                    7
                    <= len(value)
                    <= 14
                ):

                    return value

    return ""


# ============================================================
# GENERIC NUMBER VALUE
# ============================================================

def _extract_number_like_value(
    text,
    labels,
):

    value = _value_after_labels(
        text,
        labels,
        max_length=80,
    )

    if not value:
        return ""

    value = re.split(
        (
            r"\s{2,}|"
            r"(?=\b(?:VALID|EXPIR|FROM|TO|DATE)\b)"
        ),
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    return value.strip(
        " :-|#,"
    )[:60]


# ============================================================
# VEHICLE TYPE NORMALIZATION
# ============================================================

def _normalise_vehicle_type(
    value,
):

    lower = str(
        value or ""
    ).lower()

    if any(
        token in lower
        for token in (
            "motor cycle",
            "motorcycle",
            "m-cycle",
            "two wheeler",
            "bike",
        )
    ):

        return "Bike"

    if "scooter" in lower:
        return "Scooter"

    if any(
        token in lower
        for token in (
            "motor car",
            "car",
            "suv",
            "sedan",
            "hatchback",
            "lmv",
        )
    ):

        return "Car"

    return ""


# ============================================================
# FUEL NORMALIZATION
# ============================================================

def _normalise_fuel_type(
    value,
):

    lower = str(
        value or ""
    ).lower()

    if "diesel" in lower:
        return "Diesel"

    if "electric" in lower:
        return "Electric"

    if "hybrid" in lower:
        return "Hybrid"

    if "cng" in lower:
        return "CNG"

    if (
        "petrol" in lower
        or "gasoline" in lower
    ):
        return "Petrol"

    return ""


# ============================================================
# MONEY EXTRACTION
# ============================================================

def _extract_money(
    value,
):

    raw = str(
        value or ""
    ).replace(
        ",",
        "",
    )

    match = re.search(
        (
            r"(?:₹|RS\.?|INR)?\s*"
            r"(\d+(?:\.\d{1,2})?)"
        ),
        raw,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    return match.group(1)


# ============================================================
# EMPTY RESPONSE STRUCTURE
# ============================================================

def _empty_details():

    return {
        "registration_number": "",
        "vehicle_name": "",
        "company": "",
        "model": "",
        "variant": "",
        "vehicle_type": "",
        "fuel_type": "",
        "transmission": "",
        "manufacturing_year": "",
        "insurance": {
            "provider": "",
            "policy_number": "",
            "start_date": "",
            "expiry": "",
            "premium": "",
        },
        "puc": {
            "certificate_number": "",
            "issue_date": "",
            "expiry": "",
        },
    }


# ============================================================
# MERGE RESULTS
# ============================================================

def _merge_non_empty(
    destination,
    source,
):

    for key, value in source.items():

        if isinstance(
            value,
            dict,
        ):

            destination.setdefault(
                key,
                {},
            )

            _merge_non_empty(
                destination[key],
                value,
            )

        elif (
            value not in (
                "",
                None,
            )
            and destination.get(
                key
            )
            in (
                "",
                None,
            )
        ):

            destination[
                key
            ] = value


# ============================================================
# PARSE DOCUMENT TEXT
# ============================================================

def _parse_vehicle_document_text(
    text,
    document_type,
):

    details = _empty_details()

    # --------------------------------------------------------
    # Registration Number
    # --------------------------------------------------------

    details[
        "registration_number"
    ] = _extract_registration_number(
        text
    )

    # --------------------------------------------------------
    # Manufacturer
    # --------------------------------------------------------

    company = _value_after_labels(
        text,
        (
            r"\bMAKER'?S?\s*NAME\b",
            r"\bMANUFACTURER\b",
            r"\bMAKE\b",
        ),
    )

    details[
        "company"
    ] = _normalise_whitespace(
        company
    )[:100]

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = _value_after_labels(
        text,
        (
            r"\bMAKER'?S?\s*MODEL\b",
            r"\bMODEL\s*NAME\b",
            r"\bMODEL\b",
        ),
    )

    details[
        "model"
    ] = _normalise_whitespace(
        model
    )[:100]

    # --------------------------------------------------------
    # Vehicle Name
    # --------------------------------------------------------

    details[
        "vehicle_name"
    ] = (
        details["model"]
        or details["company"]
        or details[
            "registration_number"
        ]
    )

    # --------------------------------------------------------
    # Variant
    # --------------------------------------------------------

    details[
        "variant"
    ] = _normalise_whitespace(
        _value_after_labels(
            text,
            (
                r"\bVARIANT\b",
                r"\bVERSION\b",
            ),
        )
    )[:100]

    # --------------------------------------------------------
    # Vehicle Type
    # --------------------------------------------------------

    vehicle_class = (
        _value_after_labels(
            text,
            (
                r"\bCLASS\s*OF\s*VEHICLE\b",
                r"\bVEHICLE\s*CLASS\b",
                r"\bBODY\s*TYPE\b",
            ),
        )
    )

    details[
        "vehicle_type"
    ] = _normalise_vehicle_type(
        vehicle_class
    )

    # --------------------------------------------------------
    # Fuel
    # --------------------------------------------------------

    fuel = _value_after_labels(
        text,
        (
            r"\bFUEL\s*USED\b",
            r"\bFUEL\s*TYPE\b",
            r"\bFUEL\b",
        ),
    )

    details[
        "fuel_type"
    ] = _normalise_fuel_type(
        fuel
    )

    # --------------------------------------------------------
    # Transmission
    # --------------------------------------------------------

    transmission = (
        _value_after_labels(
            text,
            (
                r"\bTRANSMISSION\b",
                r"\bGEARBOX\b",
            ),
        )
    )

    transmission_lower = (
        transmission.lower()
    )

    if "auto" in transmission_lower:

        details[
            "transmission"
        ] = "Automatic"

    elif "manual" in transmission_lower:

        details[
            "transmission"
        ] = "Manual"

    # --------------------------------------------------------
    # Manufacturing Year
    # --------------------------------------------------------

    manufacturing = (
        _value_after_labels(
            text,
            (
                (
                    r"\bMONTH\s*/?\s*YEAR"
                    r"\s*OF\s*MFG\b"
                ),
                (
                    r"\bMANUFACTURING"
                    r"\s*DATE\b"
                ),
                r"\bMFG\s*DATE\b",
                r"\bMFG\s*YEAR\b",
            ),
        )
    )

    details[
        "manufacturing_year"
    ] = _extract_year(
        manufacturing
    )

    # ========================================================
    # INSURANCE DETAILS
    # ========================================================

    insurance_provider = (
        _value_after_labels(
            text,
            (
                r"\bINSURANCE\s*COMPANY\b",
                r"\bINSURER\s*NAME\b",
                r"\bNAME\s*OF\s*INSURER\b",
            ),
        )
    )

    details[
        "insurance"
    ][
        "provider"
    ] = _normalise_whitespace(
        insurance_provider
    )[:120]

    policy_number = (
        _extract_number_like_value(
            text,
            (
                (
                    r"\bINSURANCE\s*POLICY\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
                (
                    r"\bPOLICY\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
            ),
        )
    )

    details[
        "insurance"
    ][
        "policy_number"
    ] = policy_number

    insurance_start = (
        _value_after_labels(
            text,
            (
                (
                    r"\bINSURANCE\s*"
                    r"(?:START|FROM)\s*DATE\b"
                ),
                (
                    r"\bPOLICY\s*"
                    r"(?:START|FROM)\s*DATE\b"
                ),
            ),
        )
    )

    details[
        "insurance"
    ][
        "start_date"
    ] = _extract_date(
        insurance_start
    )

    insurance_expiry = (
        _value_after_labels(
            text,
            (
                (
                    r"\bINSURANCE\s*"
                    r"EXPIRY\s*DATE\b"
                ),
                (
                    r"\bINSURANCE\s*"
                    r"VALID(?:ITY)?\s*"
                    r"(?:UPTO|UP\s*TO)?\b"
                ),
                (
                    r"\bPOLICY\s*"
                    r"EXPIRY\s*DATE\b"
                ),
            ),
        )
    )

    details[
        "insurance"
    ][
        "expiry"
    ] = _extract_date(
        insurance_expiry
    )

    premium = _value_after_labels(
        text,
        (
            r"\bTOTAL\s*PREMIUM\b",
            r"\bGROSS\s*PREMIUM\b",
            r"\bPREMIUM\s*AMOUNT\b",
            r"\bPREMIUM\b",
        ),
    )

    details[
        "insurance"
    ][
        "premium"
    ] = _extract_money(
        premium
    )

    # ========================================================
    # PUC DETAILS
    # ========================================================

    puc_number = (
        _extract_number_like_value(
            text,
            (
                (
                    r"\bPUCC?\s*CERTIFICATE\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
                (
                    r"\bPUCC?\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
                (
                    r"\bPOLLUTION\s*CONTROL\s*"
                    r"CERTIFICATE\s*"
                    r"(?:NO|NUMBER|NO\.)\b"
                ),
            ),
        )
    )

    details[
        "puc"
    ][
        "certificate_number"
    ] = puc_number

    puc_issue = (
        _value_after_labels(
            text,
            (
                r"\bPUCC?\s*ISSUE\s*DATE\b",
                (
                    r"\bPOLLUTION\s*CONTROL\s*"
                    r"ISSUE\s*DATE\b"
                ),
                r"\bDATE\s*OF\s*ISSUE\b",
            ),
        )
    )

    details[
        "puc"
    ][
        "issue_date"
    ] = _extract_date(
        puc_issue
    )

    puc_expiry = (
        _value_after_labels(
            text,
            (
                (
                    r"\bPUCC?\s*"
                    r"EXPIRY\s*DATE\b"
                ),
                (
                    r"\bPUCC?\s*VALID(?:ITY)?"
                    r"\s*(?:UPTO|UP\s*TO)?\b"
                ),
                (
                    r"\bPOLLUTION\s*CONTROL\s*"
                    r"EXPIRY\s*DATE\b"
                ),
            ),
        )
    )

    details[
        "puc"
    ][
        "expiry"
    ] = _extract_date(
        puc_expiry
    )

    return details


# ============================================================
# COUNT EXTRACTED FIELDS
# ============================================================

def _count_extracted_fields(
    details,
):

    count = 0

    for value in details.values():

        if isinstance(
            value,
            dict,
        ):

            count += sum(
                1
                for item in value.values()
                if item not in (
                    "",
                    None,
                )
            )

        elif value not in (
            "",
            None,
        ):

            count += 1

    return count


# ============================================================
# MAIN FUNCTION USED BY vehicle.py
# ============================================================

def extract_vehicle_documents(
    uploaded_files,
):

    files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if uploaded_file
        and getattr(
            uploaded_file,
            "filename",
            "",
        )
    ]

    if not files:

        raise DocumentExtractionError(
            "Choose at least one RC, "
            "insurance or PUC document."
        )

    if len(files) > MAX_DOCUMENT_COUNT:

        raise DocumentExtractionError(
            "Upload a maximum of 3 files."
        )

    combined_details = (
        _empty_details()
    )

    processed_documents = []

    warnings = []

    # ========================================================
    # PROCESS EACH FILE
    # ========================================================

    for uploaded_file in files:

        filename = Path(
            uploaded_file.filename
        ).name

        extension = Path(
            filename
        ).suffix.lower()

        if (
            extension
            not in
            ALLOWED_DOCUMENT_EXTENSIONS
        ):

            raise DocumentExtractionError(
                f"{filename}: unsupported file type. "
                "Use PDF, PNG, JPG, JPEG or WEBP."
            )

        file_bytes = (
            uploaded_file.read()
        )

        if not file_bytes:

            raise DocumentExtractionError(
                f"{filename}: file is empty."
            )

        if (
            len(file_bytes)
            > MAX_SINGLE_DOCUMENT_BYTES
        ):

            raise DocumentExtractionError(
                f"{filename}: file is larger than 8 MB."
            )

        try:

            # -----------------------------------------------
            # PDF
            # -----------------------------------------------

            if extension == ".pdf":

                text = (
                    _extract_text_from_pdf(
                        file_bytes
                    )
                )

                extraction_method = (
                    "PDF text extraction"
                )

            # -----------------------------------------------
            # IMAGE
            # -----------------------------------------------

            else:

                text = (
                    _extract_text_from_image(
                        file_bytes
                    )
                )

                extraction_method = (
                    "OCR"
                )

        except DocumentExtractionError as exc:

            warnings.append(
                f"{filename}: {exc}"
            )

            continue

        document_type = (
            _detect_document_type(
                text
            )
        )

        parsed_details = (
            _parse_vehicle_document_text(
                text,
                document_type,
            )
        )

        _merge_non_empty(
            combined_details,
            parsed_details,
        )

        processed_documents.append(
            {
                "filename":
                    filename,

                "document_type":
                    document_type,

                "method":
                    extraction_method,

                "fields_found":
                    _count_extracted_fields(
                        parsed_details
                    ),
            }
        )

    # ========================================================
    # VALIDATE RESULTS
    # ========================================================

    if not processed_documents:

        raise DocumentExtractionError(
            warnings[0]
            if warnings
            else "No document could be processed."
        )

    recognized_fields = (
        _count_extracted_fields(
            combined_details
        )
    )

    if recognized_fields == 0:

        raise DocumentExtractionError(
            "The document was read, but no vehicle, "
            "insurance or PUC fields were identified. "
            "Try a clearer document."
        )

    # ========================================================
    # RETURN TO routes/vehicle.py
    # ========================================================

    return {
        "details":
            combined_details,

        "documents":
            processed_documents,

        "warnings":
            warnings,

        "recognized_fields":
            recognized_fields,
    }