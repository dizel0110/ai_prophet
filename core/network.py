import socket
import logging
import os

logger = logging.getLogger(__name__)

def apply_dns_patch():
    """
    Минималистичный сетевой мост:
    На Hugging Face полностью полагаемся на системный DNS.
    Патчи отключены во избежание конфликтов SSL и сетевой изоляции.
    """
    # НА HF SPACES: отключаем патч, используем системный DNS
    if os.getenv("SPACE_ID"):
        logger.info("✅ Hugging Face Native Network Mode: Active (системный DNS)")
        return True

    # ЛОКАЛЬНО: статический DNS для Telegram и YouTube
    original_getaddrinfo = socket.getaddrinfo

    STATIC_IPS = {
        'api.telegram.org': '149.154.167.220',
        'www.youtube.com': '142.250.180.228',
        'youtube.com': '142.250.180.228'
    }

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if host in STATIC_IPS:
            return original_getaddrinfo(STATIC_IPS[host], port, socket.AF_INET, type, proto, flags)
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo
    logger.info("✨ PROPHET STATIC DNS: Local Shield Activated")
    return True
