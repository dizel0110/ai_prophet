import socket
import logging
import dns.resolver
import sys
import os

logger = logging.getLogger(__name__)

def apply_dns_patch():
    """
    Умный патч DNS: работает локально через обходные пути и 
    адаптируется под ограничения Hugging Face Spaces.
    """
    try:
        # 1. Проверяем, нужна ли помощь (видит ли система Telegram)
        try:
            socket.getaddrinfo('api.telegram.org', 443)
            # Если дошли сюда, системный DNS работает
            if not os.getenv("SPACE_ID"): # Локально всё равно патчим для YouTube
                 logger.info("✅ System DNS works for Telegram, but applying patch for YouTube/Stability")
            else:
                 logger.info("✅ System DNS is healthy on HF. Patching restricted.")
                 return True
        except Exception:
            logger.info("⚠️ System DNS lookup failed. Activating Prophet DNS Recovery...")

        # 2. Настраиваем альтернативный резолвер
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '1.1.1.1', '1.0.0.1']
        resolver.timeout = 2
        resolver.lifetime = 2

        original_getaddrinfo = socket.getaddrinfo

        def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            # Список хостов, для которых мы будем искать обходные пути
            target_hosts = ['api.telegram.org', 'www.youtube.com', 'youtube.com']
            
            is_target = any(host == h or host.endswith('.' + h) for h in target_hosts)
            
            if is_target:
                try:
                    # Пробуем оригинальный резолвер
                    return original_getaddrinfo(host, port, family, type, proto, flags)
                except Exception:
                    # Если упало (как на HF), пробуем альтернативу через IP
                    try:
                        # Получаем IP через Public DNS
                        ans = resolver.resolve(host, 'A')
                        if ans:
                            ip = ans[0].to_text()
                            # Пытаемся подключиться по IP, но маскируем это под системный вызов
                            try:
                                return original_getaddrinfo(ip, port, socket.AF_INET, type, proto, flags)
                            except PermissionError:
                                # Если HF блокирует прямые IP (Operation not permitted)
                                # То мы бессильны, пробрасываем ошибку выше
                                raise
                    except Exception:
                        pass
            
            return original_getaddrinfo(host, port, family, type, proto, flags)

        socket.getaddrinfo = patched_getaddrinfo
        logger.info("🔮 Prophet Smart DNS Overlay Activated")
        return True

    except Exception as e:
        logger.warning(f"❌ DNS patch setup failed: {e}")
        return False
