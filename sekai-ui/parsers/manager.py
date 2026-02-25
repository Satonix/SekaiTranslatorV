from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from parsers.entries import EntryDict, new_entry
from parsers.repository import ParsersRepository


# ---------------------------------------------------------------------------
# Tipos (compat + utilitários)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParserMeta:
    id: str
    name: str
    version: str
    description: str
    extensions: list[str]


@dataclass(frozen=True)
class ParserPlugin:
    """
    Objeto que a UI espera em CreateProjectDialog / ProjectSettingsDialog.
    A UI lê:
      - plugin_id
      - name
      - extensions (set)
    """
    plugin_id: str
    name: str
    extensions: set[str]
    version: str = ""
    description: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_path_str(v: Any) -> str:
    """
    Normaliza strings / Path / os.PathLike para str.
    """
    if v is None:
        return ""
    try:
        # PathLike
        return os.fspath(v)
    except Exception:
        pass
    if isinstance(v, str):
        return v
    return str(v)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class _ParserAdapter:
    """Adapta ``sekai_parsers`` (repo Opção A) para a interface esperada pela UI/core."""

    def __init__(self, parser_proto: Any, info: Any):
        self._p = parser_proto
        self._info = info
        self.id = str(getattr(info, "id", "")) or ""
        self.name = str(getattr(info, "name", self.id)) or self.id
        self.version = str(getattr(info, "version", "")) or ""
        self.description = str(getattr(info, "description", "")) or ""
        self.extensions = list(getattr(info, "extensions", []) or [])

    # ------------------------
    # Helpers
    # ------------------------

    def _ctx_project_encoding(self, ctx: Any) -> str:
        enc = (getattr(ctx, "project", {}) or {}).get("encoding") or "utf-8"
        return str(enc)

    def _ctx_file_path(self, ctx: Any) -> str:
        """
        IMPORTANT:
        Em vários fluxos da UI o file_path pode ser pathlib.Path (PathLike).
        Se isso virar "", can_parse() falha e nenhum parser é escolhido.
        """
        for attr in ("file_path", "path", "source_path", "current_file", "filename"):
            v = getattr(ctx, attr, None)
            p = _to_path_str(v).strip()
            if p:
                return p

        # fallback: ctx dict-like
        try:
            for k in ("file_path", "path", "source_path"):
                v = ctx.get(k)  # type: ignore[attr-defined]
                p = _to_path_str(v).strip()
                if p:
                    return p
        except Exception:
            pass

        return ""

    def _encode_text(self, text: str, enc: str) -> bytes:
        try:
            return (text or "").encode(enc, errors="replace")
        except Exception:
            return (text or "").encode("utf-8", errors="replace")

    def _decode_bytes(self, data: bytes, enc: str) -> str:
        try:
            return (data or b"").decode(enc, errors="replace")
        except Exception:
            return (data or b"").decode("utf-8", errors="replace")

    # ------------------------
    # Interface esperada
    # ------------------------

    def detect(self, ctx: Any, text: str) -> float:
        """
        Usado por autodetect. Precisa acertar o file_path corretamente.
        """
        try:
            fp = self._ctx_file_path(ctx)
            enc = self._ctx_project_encoding(ctx)
            data = self._encode_text(text, enc)

            can_parse = getattr(self._p, "can_parse", None)
            if callable(can_parse):
                ok = bool(can_parse(file_path=fp, data=data))
                return 1.0 if ok else 0.0

            # fallback por extensão (se o parser não tiver can_parse)
            if fp:
                ext = "." + fp.rsplit(".", 1)[-1].lower() if "." in fp else ""
                exts = {str(e).lower() for e in (getattr(self._p, "extensions", None) or ())}
                return 1.0 if (ext and ext in exts) else 0.0

            return 0.0
        except Exception:
            return 0.0

    def parse(self, ctx: Any, text: str) -> list[EntryDict]:
        """
        Converte o parse do engine para EntryDict do SekaiTranslatorV UI.

        Suporta:
        - formato antigo: res.blocks
        - formato novo: ParseResult(entries=...)
        """
        fp = self._ctx_file_path(ctx)
        enc = self._ctx_project_encoding(ctx)
        data = self._encode_text(text, enc)

        # parse signature (repo atual): parse(data: bytes, *, file_path: Optional[str])
        res = self._p.parse(data=data, file_path=fp)

        out: list[EntryDict] = []

        # Alguns parsers podem retornar diretamente uma lista (de blocks/entries)
        # em vez de um objeto com .blocks/.entries.
        if isinstance(res, (list, tuple)):
            seq = list(res)
            if not seq:
                return out

            first = seq[0]

            # lista de blocks (antigo)
            if hasattr(first, "text") and hasattr(first, "translatable"):
                for i, b in enumerate(seq):
                    if not getattr(b, "translatable", True):
                        continue
                    entry_id = str(getattr(b, "block_id", "") or f"{i}")
                    speaker = getattr(b, "speaker", None)
                    meta = getattr(b, "meta", None) or {}
                    out.append(
                        new_entry(
                            id=entry_id,
                            entry_id=entry_id,
                            original=str(getattr(b, "text", "")),
                            translation="",
                            speaker=str(speaker) if speaker else "",
                            meta=dict(meta),
                        )
                    )
                return out

            # lista de entries (novo)
            if hasattr(first, "key") and hasattr(first, "text"):
                for e in seq:
                    entry_id = str(getattr(e, "key", "") or "")
                    if not entry_id:
                        continue
                    speaker = getattr(e, "speaker", None)
                    meta = getattr(e, "meta", None) or {}
                    out.append(
                        new_entry(
                            id=entry_id,
                            entry_id=entry_id,
                            original=str(getattr(e, "text", "") or ""),
                            translation="",
                            speaker=str(speaker) if speaker else "",
                            meta=dict(meta),
                        )
                    )
                return out

            # lista de dicts no formato EntryDict
            if isinstance(first, dict) and ("original" in first or "text" in first):
                for i, d in enumerate(seq):
                    if not isinstance(d, dict):
                        continue
                    entry_id = str(d.get("id") or d.get("entry_id") or f"{i}")
                    original = d.get("original")
                    if original is None:
                        original = d.get("text")
                    out.append(
                        new_entry(
                            id=entry_id,
                            entry_id=str(d.get("entry_id") or entry_id),
                            original=str(original or ""),
                            translation=str(d.get("translation") or ""),
                            speaker=str(d.get("speaker") or ""),
                            meta=dict(d.get("meta") or {}),
                        )
                    )
                return out

            # lista de tuplas (key, text, speaker?, meta?)
            if isinstance(first, (list, tuple)) and len(first) >= 2:
                for t in seq:
                    if not isinstance(t, (list, tuple)) or len(t) < 2:
                        continue
                    entry_id = str(t[0] or "")
                    if not entry_id:
                        continue
                    txt = t[1]
                    speaker = t[2] if len(t) >= 3 else ""
                    meta = t[3] if len(t) >= 4 and isinstance(t[3], dict) else {}
                    out.append(
                        new_entry(
                            id=entry_id,
                            entry_id=entry_id,
                            original=str(txt or ""),
                            translation="",
                            speaker=str(speaker or ""),
                            meta=dict(meta or {}),
                        )
                    )
                return out


        # --------
        # Formato antigo (blocks)
        # --------
        blocks = getattr(res, "blocks", None)
        if blocks is not None:
            for i, b in enumerate(blocks):
                if not getattr(b, "translatable", True):
                    continue
                entry_id = str(getattr(b, "block_id", "") or f"{i}")
                speaker = getattr(b, "speaker", None)
                meta = getattr(b, "meta", None) or {}
                out.append(
                    new_entry(
                        id=entry_id,
                        entry_id=entry_id,
                        original=str(getattr(b, "text", "")),
                        translation="",
                        speaker=str(speaker) if speaker else "",
                        meta=dict(meta),
                    )
                )
            return out

        # --------
        # Formato novo (ParseResult.entries)
        # sekai_parsers.api.Entry = (key, text, speaker, meta)
        # --------
        entries = getattr(res, "entries", None)
        if entries is not None:
            for e in entries:
                entry_id = str(getattr(e, "key", "") or "")
                if not entry_id:
                    continue
                speaker = getattr(e, "speaker", None)
                meta = getattr(e, "meta", None) or {}
                out.append(
                    new_entry(
                        id=entry_id,
                        entry_id=entry_id,
                        original=str(getattr(e, "text", "") or ""),
                        translation="",
                        speaker=str(speaker) if speaker else "",
                        meta=dict(meta),
                    )
                )
            return out

        return out

    def rebuild(self, ctx: Any, entries: list[EntryDict]) -> str:
        """
        Reconstrói texto final.

        Suporta:
        - formato antigo: compile(blocks, meta)
        - formato novo: export(data, entries, file_path=...)
        """
        fp = self._ctx_file_path(ctx)
        enc = self._ctx_project_encoding(ctx)

        original_text = getattr(ctx, "original_text", None)
        if original_text is None:
            original_text = getattr(ctx, "original", None) or getattr(ctx, "text", None) or ""

        original_bytes = self._encode_text(str(original_text or ""), enc)

        # ----- antigo: compile()
        compile_fn = getattr(self._p, "compile", None)
        if callable(compile_fn):
            parsed = self._p.parse(data=original_bytes, file_path=fp)

            by_id: dict[str, str] = {}
            for e in entries:
                eid = str(e.get("id") or "")
                if not eid:
                    continue
                t = e.get("translation")
                if t is None or str(t) == "":
                    t = e.get("_last_committed_translation") or ""
                t = str(t)
                by_id[eid] = t

            compiled_blocks = []
            for b in getattr(parsed, "blocks", []) or []:
                if not getattr(b, "translatable", True):
                    compiled_blocks.append(b)
                    continue

                bid = str(getattr(b, "block_id", "") or "")
                if bid and bid in by_id and by_id[bid] != "":
                    try:
                        compiled_blocks.append(
                            type(b)(
                                block_id=b.block_id,
                                text=by_id[bid],
                                speaker=getattr(b, "speaker", None),
                                translatable=True,
                                meta=getattr(b, "meta", None),
                            )
                        )
                    except Exception:
                        b.text = by_id[bid]
                        compiled_blocks.append(b)
                else:
                    compiled_blocks.append(b)

            compile_res = compile_fn(
                file_path=fp,
                blocks=compiled_blocks,
                meta=getattr(parsed, "meta", None),
            )
            data_out = bytes(getattr(compile_res, "data", b"") or b"")
            return self._decode_bytes(data_out, enc)

        # ----- novo: export(data, entries, file_path=...)
        export_fn = getattr(self._p, "export", None)
        if callable(export_fn):
            parsed = self._p.parse(data=original_bytes, file_path=fp)

            # map key -> replacement text (translation if present else original)
            by_key: dict[str, str] = {}
            for d in entries:
                k = str(d.get("id") or "")
                if not k:
                    continue
                tr = d.get("translation")
                if tr is None or str(tr) == "":
                    tr = d.get("_last_committed_translation")
                if tr is not None and str(tr) != "":
                    by_key[k] = str(tr)
                else:
                    by_key[k] = str(d.get("original") or "")

            # sekai_parsers.api.Entry expects (key, text, speaker, meta)
            class _E:
                __slots__ = ("key", "text", "speaker", "meta")

                def __init__(self, key: str, text: str, speaker: str | None, meta: dict):
                    self.key = key
                    self.text = text
                    self.speaker = speaker
                    self.meta = meta

            parsed_entries = getattr(parsed, "entries", []) or []
            out_entries: list[Any] = []
            for pe in parsed_entries:
                k = str(getattr(pe, "key", "") or "")
                if not k:
                    continue
                orig = str(getattr(pe, "text", "") or "")
                spk = getattr(pe, "speaker", None)
                meta = getattr(pe, "meta", None) or {}
                repl = by_key.get(k, orig)
                out_entries.append(_E(k, repl, spk, dict(meta)))

            data_out = export_fn(original_bytes, out_entries, file_path=fp)
            if isinstance(data_out, str):
                return data_out
            return self._decode_bytes(bytes(data_out), enc)

        return str(original_text or "")


# ---------------------------------------------------------------------------
# Backend engines
# ---------------------------------------------------------------------------

class _EnginesBackend:
    """
    Backend mínimo para o formato Opção A:
      - sekai_parsers.list_engines()
      - sekai_parsers.get_engine(engine_id)
    """

    def __init__(self, sekai_parsers_mod: Any):
        self._m = sekai_parsers_mod

    def list_ids(self) -> list[str]:
        try:
            return list(self._m.list_engines())
        except Exception:
            return []

    def get(self, engine_id: str) -> Any:
        return self._m.get_engine(engine_id)

    def detect(self, file_path: str, data: bytes) -> Optional[str]:
        best_id: Optional[str] = None
        best_score = 0.0

        fp = _to_path_str(file_path)

        for eid in self.list_ids():
            try:
                p = self.get(eid)
                can_parse = getattr(p, "can_parse", None)
                if callable(can_parse):
                    score = 1.0 if bool(can_parse(file_path=fp, data=data)) else 0.0
                else:
                    score = 0.0
            except Exception:
                score = 0.0

            if score > best_score:
                best_score = score
                best_id = eid
                if best_score >= 1.0:
                    break

        return best_id


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class ParserManager:
    """Lista e fornece parsers a partir do repo externo (Opção A: sekai_parsers engines)."""

    def __init__(self, repo: ParsersRepository):
        self._repo = repo
        self._backend: Optional[_EnginesBackend] = None
        self._cache: dict[str, _ParserAdapter] = {}

    def _import_sekai_parsers(self):
        self._repo.ensure_importable()

        try:
            import sekai_parsers  # type: ignore
        except Exception as e:
            st = None
            try:
                st = self._repo.status()
            except Exception:
                st = None

            extra = ""
            if st is not None:
                extra = f" (repo_dir={st.repo_dir} src_dir={st.src_dir})"
            raise RuntimeError(f"Falha ao importar sekai_parsers do repo: {e}{extra}") from e

        try:
            if hasattr(sekai_parsers, "discover_engines"):
                sekai_parsers.discover_engines()
        except Exception:
            pass

        return sekai_parsers

    def _ensure_backend(self) -> _EnginesBackend:
        if self._backend is not None:
            return self._backend

        sp = self._import_sekai_parsers()
        self._backend = _EnginesBackend(sp)
        return self._backend

    # ------------------------------------------------------------------
    # Listagem
    # ------------------------------------------------------------------

    def list_available(self) -> list[dict]:
        be = self._ensure_backend()
        out: list[dict] = []

        for eid in be.list_ids():
            # IMPORTANT:
            # engine_id pode conter sufixos (ex: kirikiri.ks.yandere).
            # Não derive extensões do engine_id. Use engine.extensions.
            exts: list[str] = []
            try:
                proto = be.get(eid)
                exts_raw = getattr(proto, "extensions", None) or ()
                exts = [str(x).strip().lower() for x in exts_raw if str(x).strip()]
            except Exception:
                exts = []

            out.append(
                {
                    "id": eid,
                    "name": eid,
                    "version": "",
                    "description": "",
                    "extensions": exts,
                }
            )

        return out

    # ------------------------------------------------------------------
    # Recuperação / detecção
    # ------------------------------------------------------------------

    def get_parser(self, parser_id: str) -> Optional[_ParserAdapter]:
        parser_id = (parser_id or "").strip()
        if not parser_id:
            return None
        if parser_id in self._cache:
            return self._cache[parser_id]

        be = self._ensure_backend()

        try:
            proto = be.get(parser_id)
        except Exception:
            return None

        class _Info:
            def __init__(self, id_: str, proto_: Any):
                self.id = id_
                self.name = id_
                self.version = ""
                self.description = ""
                exts_raw = getattr(proto_, "extensions", None) or ()
                self.extensions = [str(x).strip().lower() for x in exts_raw if str(x).strip()]

        info = _Info(parser_id, proto)
        adapter = _ParserAdapter(proto, info)
        self._cache[parser_id] = adapter
        return adapter

    def detect_parser_id(self, file_path: Any, data: bytes) -> Optional[str]:
        be = self._ensure_backend()

        fp = _to_path_str(file_path).strip()

        # 1) tentativa normal: can_parse()
        try:
            detected = be.detect(file_path=fp, data=data)
            if detected:
                return detected
        except Exception:
            pass

        # 2) fallback por extensão do arquivo
        fp_low = fp.lower()
        dot = fp_low.rfind(".")
        ext = fp_low[dot:] if dot != -1 else ""

        if ext:
            for eid in be.list_ids():
                try:
                    proto = be.get(eid)
                    exts_raw = getattr(proto, "extensions", None) or ()
                    exts = {str(x).strip().lower() for x in exts_raw if str(x).strip()}
                    if ext in exts:
                        return eid
                except Exception:
                    continue

        return None

    # ------------------------------------------------------------------
    # Compatibilidade com a UI (CreateProjectDialog / ProjectSettingsDialog)
    # ------------------------------------------------------------------

    def all_plugins(self) -> list[ParserPlugin]:
        plugins: list[ParserPlugin] = []
        for d in self.list_available():
            pid = str(d.get("id") or "").strip()
            if not pid:
                continue

            name = str(d.get("name") or pid).strip() or pid
            exts_raw = d.get("extensions") or []
            exts_set = {str(e).strip().lower() for e in exts_raw if str(e).strip()}

            plugins.append(
                ParserPlugin(
                    plugin_id=pid,
                    name=name,
                    extensions=exts_set,
                    version=str(d.get("version") or ""),
                    description=str(d.get("description") or ""),
                )
            )
        return plugins

    def list_parsers(self) -> list[dict]:
        return self.list_available()

    def update_repo_from_github(self) -> None:
        self._repo.ensure_repo()
        self._repo.ensure_importable()
        self._backend = None
        self._cache.clear()


# ---------------------------------------------------------------------------
# Singleton (UI expects this)
# ---------------------------------------------------------------------------

_PARSER_MANAGER_SINGLETON: Optional[ParserManager] = None


def get_parser_manager(repo_url: str | None = None, force_reload: bool = False) -> ParserManager:
    global _PARSER_MANAGER_SINGLETON

    if _PARSER_MANAGER_SINGLETON is not None and not force_reload:
        return _PARSER_MANAGER_SINGLETON

    url = (repo_url or "https://github.com/Satonix/SekaiTranslatorVParsers").strip()
    repo = ParsersRepository(repo_url=url)
    _PARSER_MANAGER_SINGLETON = ParserManager(repo)
    return _PARSER_MANAGER_SINGLETON


def reload_parsers(repo_url: str | None = None) -> ParserManager:
    mgr = get_parser_manager(repo_url=repo_url, force_reload=True)
    try:
        mgr.update_repo_from_github()
    except Exception:
        pass
    return mgr