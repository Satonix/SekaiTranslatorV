from __future__ import annotations

from dataclasses import dataclass
import codecs


@dataclass(frozen=True, slots=True)
class DecodedText:
    text: str
    newline_style: str  # "\n" or "\r\n"
    had_bom: bool = False


class EncodingService:
    """Small helper for consistent decode/encode + newline handling."""

    # ----------------------------
    # File IO helpers
    # ----------------------------

    @staticmethod
    def read_bytes(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    @staticmethod
    def write_bytes(path: str, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    @staticmethod
    def read_text(path: str, encoding: str, *, errors: str = "strict") -> DecodedText:
        data = EncodingService.read_bytes(path)
        return EncodingService.decode_bytes(data, encoding, errors=errors)

    # ----------------------------
    # Newlines
    # ----------------------------

    @staticmethod
    def detect_newline_style_bytes(data: bytes) -> str:
        return "\r\n" if b"\r\n" in (data or b"") else "\n"

    @staticmethod
    def detect_newline_style_text(text: str) -> str:
        return "\r\n" if "\r\n" in (text or "") else "\n"

    @staticmethod
    def normalize_newlines(text: str, newline_style: str) -> str:
        if not text:
            return ""
        s = text.replace("\r\n", "\n").replace("\r", "\n")
        if newline_style == "\r\n":
            s = s.replace("\n", "\r\n")
        return s

    # ----------------------------
    # Decode
    # ----------------------------

    @staticmethod
    def decode_bytes(data: bytes, encoding: str, *, errors: str = "strict") -> DecodedText:
        b = data or b""
        newline_style = EncodingService.detect_newline_style_bytes(b)

        enc = (encoding or "").strip() or "utf-8"
        low = enc.lower().replace("_", "-")

        # map aliases commonly used elsewhere
        if low in ("utf-8-sig", "utf8-sig"):
            enc = "utf-8-sig"
        elif low in ("utf-16le", "utf16le"):
            enc = "utf-16-le"
        elif low in ("utf-16be", "utf16be"):
            enc = "utf-16-be"

        had_bom = False
        if b.startswith(codecs.BOM_UTF8):
            had_bom = True
        if b.startswith(codecs.BOM_UTF16_LE) or b.startswith(codecs.BOM_UTF16_BE):
            had_bom = True

        txt = b.decode(enc, errors=errors)
        return DecodedText(text=txt, newline_style=newline_style, had_bom=had_bom)

    # ----------------------------
    # Encode
    # ----------------------------

    @staticmethod
    def encode_text(
        text: str,
        encoding: str,
        *,
        newline_style: str | None = None,
        errors: str = "replace",
        add_bom: bool = False,
    ) -> bytes:
        """
        Encode text using a chosen encoding, optionally preserving newline style.

        IMPORTANT:
        - BOM is controlled by add_bom (not by encoding string).
        - Backward-compat: accepts encoding aliases like 'utf-16-le-bom' and
          converts them to (utf-16-le, add_bom=True) internally.
        """
        enc = (encoding or "").strip() or "utf-8"
        s = text or ""

        if newline_style:
            s = EncodingService.normalize_newlines(s, newline_style)

        low = enc.lower().replace("_", "-")

        # Back-compat: virtual encodings that bake BOM into the name
        if low in ("utf-16-le-bom", "utf16-le-bom", "utf-16le-bom", "utf16le-bom"):
            enc = "utf-16-le"
            add_bom = True
            low = "utf-16-le"
        elif low in ("utf-16-be-bom", "utf16-be-bom", "utf-16be-bom", "utf16be-bom"):
            enc = "utf-16-be"
            add_bom = True
            low = "utf-16-be"
        elif low in ("utf-8-sig", "utf8-sig"):
            enc = "utf-8"
            add_bom = True
            low = "utf-8"

        # Standard encode
        data = s.encode(enc, errors=errors)

        if not add_bom:
            return data

        # Prepend BOM where applicable
        if low in ("utf-8", "utf8"):
            return codecs.BOM_UTF8 + data
        if low in ("utf-16", "utf16"):
            # python utf-16 already includes BOM; but we don't want double BOM
            return s.encode("utf-16", errors=errors)
        if low in ("utf-16-le", "utf16-le", "utf-16le", "utf16le"):
            return codecs.BOM_UTF16_LE + data
        if low in ("utf-16-be", "utf16-be", "utf-16be", "utf16be"):
            return codecs.BOM_UTF16_BE + data

        # For other encodings, BOM is not meaningful; return as-is.
        return data