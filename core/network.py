import socket
import logging
import os

logger = logging.getLogger(__name__)

def apply_dns_patch():
    """
    Минималистичный сетевой мост: 
    На Hugging Face полностью полагаемся на системный DNS.
    Патчи отключены во избежание конфликтов SSL.
    """
    if os.getenv("SPACE_ID"):
        logger.info("✅ Hugging Face Native Network Mode: Active")
        return True
        
    # Локально тоже не мешаем, если не попросят
    logger.info("ℹ️ Standard Network Mode: Active")
    return True
