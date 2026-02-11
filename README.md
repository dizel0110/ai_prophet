---
title: AI Prophet
emoji: 🔮
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# 🔮 AI Prophet

[![GitHub Stars](https://img.shields.io/github/stars/dizel0110/ai_prophet?style=for-the-badge&color=8b5cf6)](https://github.com/dizel0110/ai_prophet/stargazers)
[![Telegram](https://img.shields.io/badge/Telegram-Mini_App-2CA5E0?style=for-the-badge&logo=telegram)](https://t.me/ai_prophet_io_bot)
[![AI](https://img.shields.io/badge/Model-Gemini_1.5_Flash-orange?style=for-the-badge&logo=google-cloud)](https://aistudio.google.com/)

> **"The bridge between ancient wisdom and future intelligence."**

**AI Prophet** — это ультимативный ИИ-агент для Telegram, объединяющий мощь мозгa **Gemini 1.5 Flash**, гибкость **Function Calling** и премиальный визуальный опыт через **Telegram Mini App**.

---

## ✨ Ключевые особенности (Skills)

*   🧠 **Contextual Memory**: Агент помнит историю диалога, создавая ощущение реального общения.
*   👁️ **Computer Vision**: Отправьте фото, и Пророк проанализирует его в деталях.
*   🛠️ **Real-time Skills**: Бот умеет вызывать внешние инструменты (информация о времени, системные отчеты и др.) через Function Calling.
*   💎 **Premium Mini App**: Интерфейс в стиле Glassmorphism с поддержкой Haptic Feedback и синхронизацией данных.
*   🚀 **CI/CD Ready**: Автоматический деплой через GitHub Actions.

## 🛠 Технологический стек

*   **Core:** Python 3.10+, `python-telegram-bot`
*   **AI Engine:** Google Generative AI (Gemini SDK)
*   **Web:** Vanilla JS, CSS (Glassmorphism), Telegram Web App SDK
*   **DevOps:** Docker, GitHub Actions

## 🚀 Быстрый старт

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/dizel0110/ai_prophet.git
    cd ai_prophet
    ```
2.  **Настройте окружение:**
    Создайте `.env` и вставьте ваши ключи:
    ```env
    TELEGRAM_TOKEN=your_token
    GEMINI_API_KEY=your_key
    ```
3.  **Запуск:**
    ```bash
    pip install -r requirements.txt
    python bot.py
    ```

## 🏗 Структура проекта

```text
├── .github/workflows/   # Авто-деплой (GitHub Actions)
├── bot.py               # Мозг агента и логика инструментов
├── index.html           # Интерфейс Mini App (Smart Lounge)
├── Dockerfile           # Контейнеризация для хостинга
└── requirements.txt     # Зависимости проекта
```

---
*Разработано с помощью ИИ для будущего.*
