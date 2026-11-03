"""Exceções do aplicativo. As mensagens são em português e seguras para exibir ao usuário
(nunca incluem URLs completas, tokens ou caminhos sensíveis além dos escolhidos pelo usuário)."""


class MediaForgeError(Exception):
    """Base de todos os erros esperados do aplicativo."""


class OperationCancelled(MediaForgeError):
    """A operação foi cancelada pelo usuário."""


class SourcePolicyError(MediaForgeError):
    """A fonte (URL) viola a política de segurança."""


class BlockedSourceError(SourcePolicyError):
    """Fonte bloqueada por regra de produto (ex.: páginas do YouTube)."""


class DownloadError(MediaForgeError):
    """Falha ao baixar um arquivo."""


class SizeLimitError(DownloadError):
    """O arquivo excede o limite de tamanho configurado."""


class DestinationExistsError(MediaForgeError):
    """O arquivo de destino já existe e não pode ser substituído sem confirmação."""

    def __init__(self, path):
        super().__init__(f"O arquivo já existe: {path}")
        self.path = path


class PathSecurityError(MediaForgeError):
    """Tentativa de gravar fora da pasta escolhida."""


class FFmpegMissingError(MediaForgeError):
    """FFmpeg/FFprobe não encontrados."""


class MediaServiceError(MediaForgeError):
    """Falha em FFmpeg/FFprobe."""
