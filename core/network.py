import socket
import logging
import os

logger = logging.getLogger(__name__)

def apply_dns_patch():
    """
    Гибридный сетевой мост для HF Spaces:
    - Telegram: статический IP (системный DNS не работает)
    - YouTube: статический IP (для обхода блокировок)
    - Hugging Face: системный DNS (нельзя подменять IP)
    """
    original_getaddrinfo = socket.getaddrinfo

    # Статические IP только для Telegram и YouTube
    # HF Router должен идти через системный DNS!
    STATIC_IPS = {
        'api.telegram.org': '149.154.167.220',
        'www.youtube.com': '142.250.180.228',
        'youtube.com': '142.250.180.228'
    }

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # Логгируем все DNS-запросы для отладки
        logger.debug(f"DNS lookup: {host}:{port}")

        if host in STATIC_IPS:
            logger.info(f"🔒 Static IP для {host}: {STATIC_IPS[host]}")
            return original_getaddrinfo(STATIC_IPS[host], port, socket.AF_INET, type, proto, flags)

        # Для всех остальных (включая router.huggingface.co) — системный DNS
        logger.debug(f"→ Системный DNS для {host}")
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo

    env = "HF Spaces" if os.getenv("SPACE_ID") else "Local"
    logger.info(f"🌐 Hybrid DNS Mode Active ({env})")
    logger.info(f"   Static: {list(STATIC_IPS.keys())}")
    logger.info(f"   Dynamic: все остальные (вкл. HF)")
    return True
