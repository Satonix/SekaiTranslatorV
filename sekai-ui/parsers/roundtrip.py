from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoundTripDiff:
    ok: bool
    first_diff_line: int | None = None
    original_line: str | None = None
    rebuilt_line: str | None = None


def roundtrip_diff(original_text: str, rebuilt_text: str) -> RoundTripDiff:
    """Compara original vs rebuilt e retorna a primeira divergência por linha."""
    if original_text == rebuilt_text:
        return RoundTripDiff(ok=True)

    o_lines = original_text.splitlines(keepends=True)
    r_lines = rebuilt_text.splitlines(keepends=True)
    n = max(len(o_lines), len(r_lines))
    for i in range(n):
        o = o_lines[i] if i < len(o_lines) else ""
        r = r_lines[i] if i < len(r_lines) else ""
        if o != r:
            return RoundTripDiff(
                ok=False,
                first_diff_line=i,
                original_line=o,
                rebuilt_line=r,
            )

    # fallback (diferença em finais/encoding)
    return RoundTripDiff(ok=False, first_diff_line=None)
