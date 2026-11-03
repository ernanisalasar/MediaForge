"""Nomes de arquivo seguros e proteção contra path traversal."""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from mediaforge.errors import PathSecurityError

_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_ILLEGAL = re.compile(r'[<>:"|?*\x00-\x1f]')


def sanitize_filename(name: str, default: str = "arquivo", max_len: int = 150) -> str:
    """Devolve um nome de arquivo simples (sem diretórios) válido no Windows e em sistemas POSIX."""
    text = unicodedata.normalize("NFC", str(name or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf"))
    text = text.replace("\\", "/").split("/")[-1]  # descarta qualquer componente de diretório
    text = _ILLEGAL.sub("_", text)
    text = text.strip().strip(". ").lstrip(".")
    stem, ext = os.path.splitext(text)
    ext = ext[:16]
    stem = stem.strip().rstrip(". ")
    if stem.upper() in _RESERVED:
        stem = f"_{stem}"
    if not stem:
        stem = default
    stem = stem[: max(1, max_len - len(ext))]
    return stem + ext


def safe_join(base: Path, name: str) -> Path:
    """Junta `name` (sanitizado) a `base` garantindo que o resultado fica dentro de `base`."""
    base_resolved = Path(base).resolve()
    target = (base_resolved / sanitize_filename(name)).resolve()
    ensure_within(base_resolved, target)
    return target


def ensure_within(base: Path, target: Path) -> None:
    base_resolved = Path(base).resolve()
    target_resolved = Path(target).resolve()
    if base_resolved != target_resolved and base_resolved not in target_resolved.parents:
        raise PathSecurityError("O caminho de destino sai da pasta escolhida.")


def unique_path(path: Path) -> Path:
    """Se `path` existir, devolve 'nome (1).ext', 'nome (2).ext'… sem criar nada."""
    path = Path(path)
    if not path.exists():
        return path
    for i in range(1, 10_000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise PathSecurityError("Não foi possível gerar um nome livre.")
