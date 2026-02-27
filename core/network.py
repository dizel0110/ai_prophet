import socket
import logging
import dns.resolver
import os

logger = logging.getLogger(__name__)

def apply_dns_patch():
    """
    Самая стабильная версия сетевого моста:
    Использует систему по умолчанию и включается только при сбоях.
    """
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # Список хостов, за которыми мы следим
        targets = ['api.telegram.org', 'www.youtube.com', 'youtube.com', 'googlevideo.com']
        is_target = any(host == h or host.endswith('.' + h) for h in targets)

        # 1. Сначала ВСЕГДА пробуем системный резолв (AF_INET принудительно для стабильности)
        try:
            # Попытка через стандартный путь
            return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        except Exception:
            # 2. Если упало и это наш целевой хост — включаем "аварийный режим"
            if is_target:
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = ['8.8.8.8', '1.1.1.1']
                    resolver.timeout = 2
                    ans = resolver.resolve(host, 'A')
                    if ans:
                        ip = ans[0].to_text()
                        # Возвращаем IP-адрес, обернутый в системную структуру
                        return original_getaddrinfo(ip, port, socket.AF_INET, type, proto, flags)
                except Exception:
                    pass
            
            # Если ничего не помогло, пробрасываем ошибку дальше
            raise

    socket.getaddrinfo = patched_getaddrinfo
    
    status = "Hugging Face" if os.getenv("SPACE_ID") else "Standard"
    logger.info(f"🛰️ Universal Network Bridge Active ({status} Cloud Mode)")
    return True
