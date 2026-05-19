# -*- coding: utf-8 -*-
"""
Локальный тест транскрибации аудио
Генерирует WAV файл и транскрибирует через Whisper tiny локально
"""

import sys
import os
import logging
import wave
import struct
import math
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from config import TEMP_DIR, GEMINI_KEY
from core.ai_engine import transcribe_with_gemini

TEST_DIR = os.path.join(TEMP_DIR, "test_audio")
os.makedirs(TEST_DIR, exist_ok=True)


def generate_test_wav(frequency=440, duration=2, sample_rate=16000):
    """
    Генерирует WAV файл (синусоида)
    frequency: Гц (по умолчанию 440 - нота ля)
    duration: секунды
    sample_rate: Hz (16000 оптимально для Whisper)
    """
    timestamp = int(datetime.now().timestamp())
    output_path = os.path.join(TEST_DIR, f"test_{timestamp}.wav")
    
    logger.info(f"🎵 Генерация WAV: {frequency}Hz, {duration} сек, {sample_rate}Hz...")
    
    try:
        with wave.open(output_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # Моно
            wav_file.setsampwidth(2)  # 16 бит
            wav_file.setframerate(sample_rate)
            
            for i in range(int(sample_rate * duration)):
                value = 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate)
                packed = struct.pack('<h', int(value * 32767))
                wav_file.writeframes(packed)
        
        file_size = os.path.getsize(output_path)
        logger.info(f"✅ Сгенерировано: {output_path}, {file_size / 1024:.1f} KB")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        return None


def transcribe_local_whisper(audio_path):
    """
    Локальная транскрибация через Whisper tiny
    """
    try:
        logger.info("📥 Загрузка Whisper tiny модели...")
        from transformers import WhisperProcessor, WhisperForConditionalGeneration
        
        processor = WhisperProcessor.from_pretrained("openai/whisper-tiny")
        model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-tiny")
        
        logger.info(f"🎵 Обработка файла: {audio_path}")
        
        from transformers import WhisperFeatureExtractor
        import torch
        
        # Загрузка аудио
        from scipy.io import wavfile
        sample_rate, audio_data = wavfile.read(audio_path)
        
        # Ресемплинг до 16000 Hz если нужно
        if sample_rate != 16000:
            logger.info(f"🔄 Ресемплинг {sample_rate}Hz → 16000Hz...")
            from librosa import resample
            audio_data = resample(audio_data.astype(float32), orig_sr=sample_rate, target_sr=16000)
            audio_data = (audio_data * 32767).astype(np.int16)
        
        # Обработка
        inputs = processor(audio_data, sampling_rate=16000, return_tensors="pt")
        
        logger.info("🧠 Транскрибация...")
        with torch.no_grad():
            predicted_ids = model.generate(inputs.input_features)
        
        # Декодирование
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)
        result = transcription[0].strip() if transcription else ""
        
        logger.info(f"✅ Локальная транскрибация завершена")
        return result
        
    except ImportError as e:
        logger.error(f"❌ Не установлены зависимости: {e}")
        logger.info("💡 Установи: pip install transformers torch scipy librosa")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка транскрибации: {e}")
        return None


def test_gemini(audio_path):
    """Тест Gemini транскрибации"""
    if not GEMINI_KEY:
        logger.error("❌ GEMINI_API_KEY не настроен!")
        return None
    
    logger.info("\n" + "="*60)
    logger.info("🔮 ТЕСТ GEMINI")
    logger.info("="*60)
    logger.info(f"📁 Файл: {audio_path}")
    logger.info(f"📏 Размер: {os.path.getsize(audio_path) / 1024:.1f} KB")
    
    result = transcribe_with_gemini(audio_path, timeout_sec=30)
    
    if result:
        logger.info(f"✅ GEMINI: {result}")
        return result
    else:
        logger.error("❌ GEMINI не вернул результат")
        return None


def main():
    logger.info("\n" + "="*60)
    logger.info("🎤 LOCAL AUDIO TRANSCRIPTION TEST")
    logger.info("="*60)
    
    logger.info(f"\n📊 Конфигурация:")
    logger.info(f"   GEMINI_API_KEY: {'✅' if GEMINI_KEY else '❌'}")
    logger.info(f"   TEMP_DIR: {TEMP_DIR}")
    logger.info(f"   TEST_DIR: {TEST_DIR}")
    
    # Генерация аудио
    logger.info("\n🎵 ГЕНЕРАЦИЯ ТЕСТОВОГО АУДИО...")
    audio_path = generate_test_wav(frequency=440, duration=2, sample_rate=16000)
    
    if not audio_path:
        logger.error("\n❌ НЕ УДАЛОСЬ СОЗДАТЬ АУДИО!")
        sys.exit(1)
    
    results = {"gemini": None, "local_whisper": None}
    
    # Тест Gemini
    if GEMINI_KEY:
        results["gemini"] = test_gemini(audio_path)
    
    # Локальная транскрибация
    logger.info("\n" + "="*60)
    logger.info("🏠 ТЕСТ ЛОКАЛЬНОЙ ТРАНСКРИБАЦИИ (Whisper tiny)")
    logger.info("="*60)
    results["local_whisper"] = transcribe_local_whisper(audio_path)
    
    # Итоги
    logger.info("\n" + "="*60)
    logger.info("📊 ИТОГИ")
    logger.info("="*60)
    logger.info(f"   Gemini:        {'✅ ' + results['gemini'] if results['gemini'] else '❌'}")
    logger.info(f"   Local Whisper: {'✅ ' + str(results['local_whisper']) if results['local_whisper'] else '❌'}")
    
    # Файл остаётся для проверки
    logger.info(f"\n💡 Файл: {audio_path}")
    logger.info("   Можно отправить боту в Telegram для проверки")
    
    logger.info("\nТЕСТ ЗАВЕРШЁН")


if __name__ == "__main__":
    import numpy as np
    main()
