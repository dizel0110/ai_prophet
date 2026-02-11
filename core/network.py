import socket
import logging
import dns.resolver
import time
import os
import sys

logger = logging.getLogger(__name__)

def apply_dns_patch():
    # Гарантированное отключение на Windows (win32)
    if sys.platform == 'win32' or os.name == 'nt':
        logger.info("ℹ️ LOCAL MODE: DNS patch disabled for Windows compatibility.")
        return True
    
    # Только для Hugging Face / Docker (Linux)
    for i in range(3):
        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['8.8.8.8', '1.1.1.1']
            resolver.timeout = 5
            resolver.lifetime = 5
            answer = resolver.resolve('api.telegram.org', 'A')
            telegram_ip = answer[0].to_text()
            
            original_getaddrinfo = socket.getaddrinfo
            def patched_getaddrinfo(host, *args, **kwargs):
                target = telegram_ip if host == 'api.telegram.org' else host
                return original_getaddrinfo(target, *args, **kwargs)
            
            socket.getaddrinfo = patched_getaddrinfo
            logger.info(f"✅ HF MODE: DNS Patch Active: {telegram_ip}")
            return True
        except Exception as e:
            logger.warning(f"DNS Attempt {i+1} failed: {e}")
            time.sleep(2)
    return False
