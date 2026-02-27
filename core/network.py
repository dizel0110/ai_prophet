import socket
import logging
import os

logger = logging.getLogger(__name__)

def apply_dns_patch():
    """
    Классический метод статического маппинга.
    Самый надежный способ для Hugging Face, когда системный DNS 'болеет'.
    """
    original_getaddrinfo = socket.getaddrinfo

    # Список проверенных IP-адресов (Telegram, YouTube, Hugging Face)
    # Эти адреса стабильны годами.
    STATIC_IPS = {
        'api.telegram.org': '149.154.167.220',
        'www.youtube.com': '142.250.180.228',
        'youtube.com': '142.250.180.228',
        'router.huggingface.co': '3.164.110.127',
        'huggingface.co': '18.164.174.118'
    }

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # Если хост в нашем списке — подставляем проверенный IP
        if host in STATIC_IPS:
            # Важно: используем AF_INET (IPv4), чтобы избежать -5 gaierror
            return original_getaddrinfo(STATIC_IPS[host], port, socket.AF_INET, type, proto, flags)

        # Для всех остальных используем стандартный путь
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo
    
    status = "Cloud" if os.getenv("SPACE_ID") else "Local"
    logger.info(f"✨ PROPHET STATIC DNS: {status} Shield Activated")
    return True
