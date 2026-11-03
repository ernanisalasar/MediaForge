"""Política de fontes: validação de URLs e bloqueio de SSRF.

Princípios:
* Só http/https, sem credenciais embutidas na URL.
* O host é resolvido e *todos* os IPs devem ser públicos (``ipaddress.is_global``).
* A validação é repetida a cada redirecionamento e, de novo, no momento da conexão
  (ver ``download_service``), o que também cobre DNS rebinding.
* URLs do YouTube são aceitas somente pelo fluxo dedicado de vídeo individual.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from typing import Callable, Iterable
from urllib.parse import parse_qs, urlsplit

from mediaforge.errors import SourcePolicyError

STUDIO_URL = "https://studio.youtube.com/"
TAKEOUT_URL = "https://takeout.google.com/"

YOUTUBE_HOSTS = {"youtube.com", "youtu.be"}
_YOUTUBE_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_BLOCKED_HOSTNAMES = {"localhost", "metadata", "metadata.google.internal", "instance-data", "instance-data.ec2.internal"}
_BLOCKED_SUFFIXES = (".localhost", ".internal", ".local", ".localdomain", ".lan", ".home.arpa")
_METADATA_IPS = {"169.254.169.254", "169.254.170.2", "100.100.100.200", "192.0.0.192", "fd00:ec2::254"}

Resolver = Callable[[str, int], Iterable[str]]


def default_resolver(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SourcePolicyError("Não foi possível resolver o endereço do servidor.") from exc
    return [info[4][0] for info in infos]


def is_youtube_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in YOUTUBE_HOSTS)


def is_youtube_url(url: str) -> bool:
    try:
        return is_youtube_host(urlsplit(url.strip()).hostname or "")
    except ValueError:
        return False


def normalize_youtube_video_url(url: str) -> str:
    """Converte formas comuns de URL para um link canônico de vídeo individual."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise SourcePolicyError("Link do YouTube inválido.") from exc
    if parts.scheme.lower() not in ("http", "https") or not is_youtube_host(parts.hostname or ""):
        raise SourcePolicyError("Informe uma URL http:// ou https:// de um vídeo do YouTube.")
    if parts.username or parts.password or port not in (None, 80, 443):
        raise SourcePolicyError("A URL do YouTube contém credenciais ou uma porta não permitida.")

    host = (parts.hostname or "").lower().rstrip(".")
    path_parts = [part for part in parts.path.split("/") if part]
    video_id = ""
    if host == "youtu.be" or host.endswith(".youtu.be"):
        video_id = path_parts[0] if path_parts else ""
    elif path_parts == ["watch"]:
        video_id = parse_qs(parts.query).get("v", [""])[0]
    elif len(path_parts) == 2 and path_parts[0] in {"embed", "live", "shorts", "v"}:
        video_id = path_parts[1]

    if not _YOUTUBE_VIDEO_ID.fullmatch(video_id):
        raise SourcePolicyError(
            "Informe o link de um único vídeo do YouTube. Playlists e páginas de canais não são suportadas."
        )
    return f"https://www.youtube.com/watch?v={video_id}"


def redact_url(url: str) -> str:
    """Remove credenciais, query e fragmento (podem conter tokens/URLs assinadas)."""
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{host}{port}{parts.path}"
    except ValueError:
        return "(URL inválida)"


def host_of(url: str) -> str:
    try:
        return urlsplit(url.strip()).hostname or ""
    except ValueError:
        return ""


def check_ip(ip_text: str) -> None:
    """Levanta SourcePolicyError se o IP não for um endereço público roteável."""
    try:
        ip = ipaddress.ip_address(ip_text.split("%")[0])
    except ValueError as exc:
        raise SourcePolicyError("Endereço IP inválido.") from exc
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if str(ip) in _METADATA_IPS:
        raise SourcePolicyError("Destino bloqueado: serviço de metadados de nuvem.")
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified or ip.is_loopback or ip.is_link_local or not ip.is_global:
        raise SourcePolicyError(
            "Destino bloqueado: o endereço aponta para a rede local/privada, loopback ou link-local."
        )


@dataclass
class SourcePolicy:
    """Valida URLs. ``allow_private_networks`` existe apenas para testes automatizados e
    nunca é exposto na interface nem nas configurações."""

    resolver: Resolver = field(default=default_resolver)
    allow_private_networks: bool = False

    def check_resolved_ip(self, ip_text: str) -> None:
        if not self.allow_private_networks:
            check_ip(ip_text)

    def validate_url(self, url: str) -> str:
        """Valida esquema, host e IPs resolvidos. Devolve a URL normalizada (sem espaços)."""
        url = (url or "").strip()
        if not url:
            raise SourcePolicyError("Informe um link.")
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError as exc:
            raise SourcePolicyError("Link inválido.") from exc
        if parts.scheme.lower() not in ("http", "https"):
            raise SourcePolicyError("Somente links http:// ou https:// são aceitos.")
        if parts.username or parts.password:
            raise SourcePolicyError("Links com usuário/senha embutidos não são aceitos.")
        host = (parts.hostname or "").lower().rstrip(".")
        if not host:
            raise SourcePolicyError("Link sem endereço de servidor.")
        if any(ch.isspace() or ord(ch) < 32 or ch in "\\@" for ch in host):
            raise SourcePolicyError("Endereço de servidor inválido.")
        if not self.allow_private_networks and (
            host in _BLOCKED_HOSTNAMES or host.endswith(_BLOCKED_SUFFIXES)
        ):
            raise SourcePolicyError("Destino bloqueado: nome de host interno/local.")
        port = port or (443 if parts.scheme.lower() == "https" else 80)
        try:
            ips = [str(ipaddress.ip_address(host))]  # IP literal: checado diretamente
        except ValueError:
            ips = list(self.resolver(host, port))
        if not ips:
            raise SourcePolicyError("Não foi possível resolver o endereço do servidor.")
        for ip in ips:  # todos precisam ser públicos
            self.check_resolved_ip(ip)
        return url
