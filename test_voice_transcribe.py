# -*- coding: utf-8 -*-
"""
Локальный тест транскрибации голосового сообщения
Генерирует тестовый WAV и пробует транскрибировать через Gemini и HF
"""

import os
import sys
import wave
import struct
import math
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

from config import GEMINI_KEY, HF_TOKEN, TEMP_DIR
from core.ai_engine import transcribe_with_gemini, get_hf_response

TEST_AUDIO_DIR = os.path.join(TEMP_DIR, "test_voice")
os.makedirs(TEST_AUDIO_DIR, exist_ok=True)


def generate_test_voice(duration=3, sample_rate=16000, frequency=440):
    """
    Генерирует тестовый аудиофайл (синусоида, нота Ля)
    duration: секунды
    sample_rate: Hz (16000 оптимально для Whisper)
    frequency: Hz (440 = нота Ля)
    """
    timestamp = int(datetime.now().timestamp())
    output_path = os.path.join(TEST_AUDIO_DIR, f"test_voice_{timestamp}.ogg")
    
    logger.info(f"🎵 Генерация тестового аудио: {duration} сек, {frequency}Hz...")
    
    try:
        # Генерируем WAV сначала
        wav_path = output_path.replace('.ogg', '.wav')
        with wave.open(wav_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # Моно
            wav_file.setsampwidth(2)  # 16 бит
            wav_file.setframerate(sample_rate)
            
            for i in range(int(sample_rate * duration)):
                value = 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate)
                packed = struct.pack('<h', int(value * 32767))
                wav_file.writeframes(packed)
        
        logger.info(f"✅ WAV сгенерирован: {wav_path}")
        
        # Конвертируем в OGG через ffmpeg (если есть)
        try:
            import ffmpeg
            ffmpeg.input(wav_path).output(
                output_path, 
                acodec='libopus',
                ac=1,
                ar='16000'
            ).run(quiet=True, overwrite_output=True)
            
            logger.info(f"✅ OGG сконвертирован: {output_path}")
            os.remove(wav_path)
            return output_path
            
        except Exception as e:
            logger.warning(f"⚠️ ffmpeg не доступен, используем WAV: {e}")
            return wav_path
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        return None


def test_gemini_transcribe(audio_path):
    """Тест транскрибации через Gemini"""
    logger.info("\n" + "="*60)
    logger.info("💎 ТЕСТ GEMINI ТРАНСКРИБАЦИИ")
    logger.info("="*60)
    
    if not GEMINI_KEY:
        logger.error("❌ GEMINI_API_KEY не настроен!")
        return None
    
    logger.info(f"📁 Файл: {audio_path}")
    logger.info(f"📏 Размер: {os.path.getsize(audio_path) / 1024:.1f} KB")
    
    # Таймаут 90 сек для теста
    result = transcribe_with_gemini(audio_path, timeout_sec=90)
    
    if result:
        logger.info(f"✅ GEMINI: {result}")
        return result
    else:
        logger.error("❌ GEMINI не вернул результат")
        return None


def test_hf_whisper(audio_path):
    """Тест транскрибации через HF Whisper"""
    logger.info("\n" + "="*60)
    logger.info("🧿 ТЕСТ HF WHISPER")
    logger.info("="*60)
    
    if not HF_TOKEN:
        logger.error("❌ HF_TOKEN не настроен!")
        return None
    
    logger.info(f"📁 Файл: {audio_path}")
    logger.info(f"📏 Размер: {os.path.getsize(audio_path) / 1024:.1f} KB")
    
    result = get_hf_response(image_path=audio_path, task="audio")
    
    if result:
        logger.info(f"✅ HF WHISPER: {result}")
        return result
    else:
        logger.error("❌ HF WHISPER не вернул результат")
        return None


def main():
    logger.info("\n" + "="*60)
    logger.info("🎤 ТЕСТ ТРАНСКРИБАЦИИ ГОЛОСОВЫХ СООБЩЕНИЙ")
    logger.info("="*60)
    
    logger.info(f"\n📊 Конфигурация:")
    logger.info(f"   GEMINI_API_KEY: {'✅' if GEMINI_KEY else '❌'}")
    logger.info(f"   HF_TOKEN: {'✅' if HF_TOKEN else '❌'}")
    logger.info(f"   TEMP_DIR: {TEMP_DIR}")
    
    # Генерация тестового аудио
    logger.info("\n🎵 ГЕНЕРАЦИЯ ТЕСТОВОГО АУДИО...")
    audio_path = generate_test_voice(duration=3, frequency=440)
    
    if not audio_path:
        logger.error("\n❌ НЕ УДАЛОСЬ СОЗДАТЬ АУДИО!")
        sys.exit(1)
    
    results = {"gemini": None, "hf_whisper": None}
    
    # Тест Gemini
    if GEMINI_KEY:
        results["gemini"] = test_gemini_transcribe(audio_path)
    
    # Тест HF Whisper
    if HF_TOKEN:
        results["hf_whisper"] = test_hf_whisper(audio_path)
    
    # Итоги
    logger.info("\n" + "="*60)
    logger.info("📊 ИТОГИ ТЕСТА")
    logger.info("="*60)
    logger.info(f"   Gemini:     {'✅ ' + results['gemini'][:50] if results['gemini'] else '❌'}...")
    logger.info(f"   HF Whisper: {'✅ ' + str(results['hf_whisper'])[:50] if results['hf_whisper'] else '❌'}...")
    
    logger.info(f"\n💡 Файл для ручной проверки: {audio_path}")
    logger.info("   Можно отправить боту в Telegram")
    
    logger.info("\n✅ ТЕСТ ЗАВЕРШЁН")


if __name__ == "__main__":
    main()
