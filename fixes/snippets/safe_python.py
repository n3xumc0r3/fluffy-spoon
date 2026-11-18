"""Готовые безопасные примитивы для быстрого патчинга (Python 3.10+).

Копируй нужные функции в сервис. Каждая заменяет опасный паттерн:
open(join(base, user))            -> safe_path()
subprocess(..., shell=True)       -> run_noshell()
requests.get(user_url)            -> safe_get()
ET.fromstring(user_xml)           -> safe_xml_parse()
yaml.load(user_yaml)              -> safe_yaml_load()
fname = upload.filename           -> safe_upload_name()
zip.extractall(dest)              -> safe_extract_zip()
if token == expected:             -> constant_eq()
header(value_from_user)           -> sanitize_header()
"""

from __future__ import annotations

import ipaddress
import os
import posixpath
import re
import socket
import subprocess
import unicodedata
import zipfile
from urllib.parse import urlparse


class UnsafeInput(ValueError):
    pass


def safe_path(base: str, untrusted: str) -> str:
    """Путь внутри base или исключение (traversal, absolute, NUL)."""
    if not isinstance(untrusted, str) or "\x00" in untrusted:
        raise UnsafeInput("bad path")
    base_real = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_real, untrusted))
    if target != base_real and os.path.commonpath([base_real, target]) != base_real:
        raise UnsafeInput("path escapes base")
    return target


def run_noshell(cmd: list[str], timeout: float = 10, cwd: str | None = None) -> str:
    """Запуск без shell; аргументы — только список строк."""
    if not isinstance(cmd, list) or not cmd:
        raise UnsafeInput("cmd must be a non-empty list")
    if not all(isinstance(a, str) and "\x00" not in a for a in cmd):
        raise UnsafeInput("bad argv")
    p = subprocess.run(
        cmd, shell=False, cwd=cwd, timeout=timeout,
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )
    return p.stdout


def as_str(value, name: str = "value", max_len: int = 256) -> str:
    if not isinstance(value, str) or len(value) > max_len:
        raise UnsafeInput(name)
    return value


def as_int(value, name: str = "value", lo: int = -(2**31), hi: int = 2**31 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnsafeInput(name)
    if not lo <= value <= hi:
        raise UnsafeInput(name)
    return value


def assert_public_url(url: str) -> str:
    """http(s) и все адреса хоста — публичные (защита от SSRF)."""
    if not isinstance(url, str) or len(url) > 2048:
        raise UnsafeInput("bad url")
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise UnsafeInput("bad scheme")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    except socket.gaierror as e:
        raise UnsafeInput(f"dns: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise UnsafeInput("non-public address")
    return url


def safe_get(url: str, timeout: float = 5, max_redirects: int = 0, **kwargs):
    """GET с проверкой SSRF на каждом хопе вручную; редиректы по умолчанию запрещены."""
    import requests

    for _ in range(max_redirects + 1):
        assert_public_url(url)
        r = requests.get(url, timeout=timeout, allow_redirects=False, **kwargs)
        if r.status_code in (301, 302, 303, 307, 308) and max_redirects > 0:
            nxt = r.headers.get("Location")
            if not nxt:
                return r
            url = nxt
            max_redirects -= 1
            continue
        return r
    raise UnsafeInput("too many redirects")


def _reject_doctype(raw: bytes) -> None:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16", errors="ignore")
    else:
        text = raw.decode("utf-8", errors="ignore")
    low = text.lower()
    if "<!doctype" in low or "<!entity" in low:
        raise UnsafeInput("DTD/entities forbidden")


def safe_xml_parse(data: bytes | str):
    """Парсер без DTD/внешних сущностей; документы с DOCTYPE отклоняются."""
    raw = data.encode() if isinstance(data, str) else data
    _reject_doctype(raw)
    try:
        from defusedxml.ElementTree import fromstring as _fromstring
        return _fromstring(raw)
    except ImportError:
        pass
    try:
        from lxml import etree
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False,
                                 dtd_validation=False, huge_tree=False)
        return etree.fromstring(raw, parser)
    except ImportError:
        import xml.etree.ElementTree as ET
        return ET.fromstring(raw)


def safe_yaml_load(text: str):
    import yaml
    return yaml.safe_load(text)


_SAFE_NAME = re.compile(r"[A-Za-z0-9._-]{1,128}")


def safe_upload_name(filename: str, allowed_ext: set[str], fallback: str = "upload") -> str:
    """Имя файла без путей и опасных расширений; проверяй также содержимое!"""
    name = unicodedata.normalize("NFKC", filename or "")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    if not _SAFE_NAME.fullmatch(name) or ".." in name:
        raise UnsafeInput("bad filename")
    ext = posixpath.splitext(name)[1].lower()
    allowed = {e.lower() for e in allowed_ext}
    if ext not in allowed:
        raise UnsafeInput("extension not allowed")
    return name if name else fallback


def safe_extract_zip(path: str, dest: str) -> list[str]:
    """Распаковка без zip slip (symlink-члены и абсолютные пути отклоняются)."""
    out: list[str] = []
    dest_real = os.path.realpath(dest)
    os.makedirs(dest_real, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise UnsafeInput("symlink in zip")
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise UnsafeInput("zip slip")
            target = os.path.realpath(os.path.join(dest_real, name))
            if os.path.commonpath([dest_real, target]) != dest_real:
                raise UnsafeInput("zip slip")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            out.append(target)
    return out


def constant_eq(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


def sanitize_header(value: str, max_len: int = 1024) -> str:
    """Убирает CR/LF/NUL — защита от header injection/splitting."""
    if not isinstance(value, str) or len(value) > max_len:
        raise UnsafeInput("bad header")
    if any(c in value for c in "\r\n\x00"):
        raise UnsafeInput("header injection")
    return value
