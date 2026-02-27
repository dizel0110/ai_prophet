import socket
import logging
import dns.resolver
import sys
import os

logger = logging.getLogger(__name__)

def apply_dns_patch():
    """
    Адаптивный сетевой патч v3:
    1. На HF Spaces: отключает ручную подмену IP, форсирует IPv4 для стабильности.
    2. Локально: использует Public DNS для обхода блокировок.
    """
    is_hf = os.getenv("SPACE_ID") is not None
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # Список критических хостов
        target_hosts = ['api.telegram.org', 'www.youtube.com', 'youtube.com', 'googlevideo.com']
        is_target = any(host == h or host.endswith('.' + h) for h in target_hosts)

        if is_target:
            # На HF Spaces принудительно используем IPv4 (AF_INET = 2)
            # Ошибка -5 часто связана с попытками IPv6
            target_family = socket.AF_INET if is_hf or family == 0 else family
            
            try:
                # 1. Простая попытка через системный резолвер
                return original_getaddrinfo(host, port, target_family, type, proto, flags)
            except Exception as e:
                # 2. Если на HF системный резолв упал, пробуем еще раз, но без смены IP
                if is_hf:
                    logger.debug(f"HF DNS retry for {host}...")
                    return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
                
                # 3. Локально (не HF): пробуем Recovery через Public DNS (Google/Cloudflare)
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = ['8.8.8.8', '1.1.1.1']
                    resolver.timeout = 3
                    resolver.lifetime = 3
                    
                    ans = resolver.resolve(host, 'A')
                    if ans:
                        # Локально мы можем позволить себе подмену на IP
                        ip = ans[0].to_text()
                        return original_getaddrinfo(ip, port, socket.AF_INET, type, proto, flags)
                except Exception:
                    pass
        
        # Для всех остальных хостов или если патч не сработал
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo
    
    env_name = "Hugging Face" if is_hf else "Local"
    logger.info(f"🌐 Adaptive Network Logic Active ({env_name} Mode)")
    return True
