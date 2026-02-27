import socket
import logging
import dns.resolver
import time
import os
import sys

logger = logging.getLogger(__name__)

# Кэширование DNS для YouTube
_youtube_dns_cache = None

def apply_dns_patch():
    global _youtube_dns_cache

    # Патч DNS для всех платформ (на Windows используем с осторожностью)
    if sys.platform == 'win32':
        logger.info("ℹ️ Windows detected: DNS patch will be applied only as fallback")
        # На Windows часто лучше оставить системный резолвер, если нет ошибок
    
    logger.info("🔧 Applying DNS patch for YouTube/Telegram...")

    # Попытка настроить DNS резолвер
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '1.1.1.1', '1.0.0.1']
        resolver.timeout = 5
        resolver.lifetime = 5

        # Кэшируем DNS для YouTube
        try:
            answer = resolver.resolve('www.youtube.com', 'A')
            _youtube_dns_cache = answer[0].to_text()
            logger.info(f"✅ YouTube DNS: {_youtube_dns_cache}")
        except Exception as e:
            logger.warning(f"⚠️ YouTube DNS failed: {e}")

        # Кэшируем DNS для Telegram (если не Windows)
        telegram_ip = None
        if sys.platform != 'win32':
            try:
                answer = resolver.resolve('api.telegram.org', 'A')
                telegram_ip = answer[0].to_text()
                logger.info(f"✅ Telegram DNS: {telegram_ip}")
            except Exception as e:
                logger.warning(f"⚠️ Telegram DNS failed: {e}")

        original_getaddrinfo = socket.getaddrinfo

        def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            # YouTube DNS cache
            if host == 'www.youtube.com' and _youtube_dns_cache:
                return original_getaddrinfo(_youtube_dns_cache, port, family, type, proto, flags)
            if host.endswith('.youtube.com') and _youtube_dns_cache:
                return original_getaddrinfo(_youtube_dns_cache, port, family, type, proto, flags)

            # Telegram DNS (только Linux)
            if host == 'api.telegram.org' and telegram_ip:
                return original_getaddrinfo(telegram_ip, port, family, type, proto, flags)

            # Остальные хосты как обычно
            return original_getaddrinfo(host, port, family, type, proto, flags)

        socket.getaddrinfo = patched_getaddrinfo
        logger.info("✅ DNS Patch Active")
        return True

    except Exception as e:
        logger.warning(f"❌ DNS patch failed: {e}")
        return False
