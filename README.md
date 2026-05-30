---
title: AI Prophet
emoji: 🔮
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# 🔮 AI Prophet — ваш ИИ-проводник

[![GitHub Stars](https://img.shields.io/github/stars/dizel0110/ai_prophet?style=for-the-badge&color=8b5cf6)](https://github.com/dizel0110/ai_prophet/stargazers)
[![Telegram](https://img.shields.io/badge/Telegram-Mini_App-2CA5E0?style=for-the-badge&logo=telegram)](https://t.me/ai_prophet_io_bot)
[![Engine](https://img.shields.io/badge/Multimodal-Gemini_%7C_Qwen_%7C_Llama_Vision-orange?style=for-the-badge&logo=google-cloud)](https://aistudio.google.com/)
[![Secondary Engine](https://img.shields.io/badge/Fallback-HF_Router_%7C_Qwen_2.5-green?style=for-the-badge&logo=huggingface)](https://huggingface.co/)

**AI Prophet** — мультимодальный ИИ-агент в Telegram. Ядро проекта — система профильных ИИ-специалистов (агентов), которые анализируют, советуют и помогают в самых разных сферах.

На фундаменте AI Prophet уже built:

---

## ✨ Что внутри

### 🧠 Мульти-агентная система
Не один чат-бот, а команда ИИ-специалистов. Каждый — узкий эксперт со своей ролью, промптом и моделью:
- **Визуальный Диагност** — анализ фото через Llama Vision / Gemini Vision
- **Специалист по движениям** — анализ видео (извлечение кадров → vision)
- **Анкетолог** — сбор и структурирование данных
- **Эксперт по техникам** — подбор методик
- **Финальный Эксперт** — синтез → заключение

Пользователь может динамически создавать собственных специалистов под любую задачу (через `/specialist` или Mini App).

### 🖐 Массажный салон (семейный проект)
Одно из направлений на базе AI Prophet. Полный цикл:
- Анкета клиента (ШММ — 20 обязательных полей, data-driven JSON-конфиг)
- Загрузка фото спины / видео походки
- AI-диагностика (5 агентов-специалистов)
- Рекомендация техник массажа + музыки под тип процедуры
- Онлайн-запись

### 🎵 Музыкальная система
- Встроенный плеер в Mini App (Internet Archive)
- AI-рекомендация музыки под контекст
- Именные плейлисты, экспорт/импорт, загрузка своей музыки

### 🎙️ Голос и мультимодальность
- Транскрибация аудио (Whisper Turbo)
- Анализ изображений и видео
- Каждый специалист может работать с медиа

### ⚙️ Админ-панель
- Управление доступом через Telegram (по chat_id)
- Список клиентов с анкетами и результатами AI-диагностики
- Никаких логинов — идентификация через Telegram

---

## 🛠 Технологический стек

| Компонент | Технология |
|-----------|-----------|
| **Runtime** | Python 3.11+ & Aiogram 3.x & FastAPI |
| **Основной AI** | Google Gemini (gemini-3.5-flash → gemini-2.5-pro, fallback chain) |
| **Fallback AI** | Hugging Face Router (Qwen 2.5-7B, Llama 3.2-11B Vision, Whisper) |
| **Mini App** | Telegram Web App (vanilla JS, glassmorphism) |
| **Deploy** | Docker, GitHub Actions → HF Spaces + Render.com |

### Архитектура
```
Telegram Bot (polling)
  └── aiogram Dispatcher
       ├── handlers/vip.py       — доступ, админ-команды
       ├── handlers/massage.py   — анкета, диагностика, музыка
       ├── handlers/messages.py  — все сообщения, function calling
       └── handlers/limits.py    — лимиты скачивания

FastAPI (health + Mini App API)
  └── static/massage/index.html  — Telegram Mini App
  └── /api/*                     — массаж, музыка, specialists, admin

core/
  ├── ai_engine.py               — Gemini client + HF Router
  ├── tools.py                   — web search, media search, download
  ├── agents/                    — мульти-агентная система
  │   ├── agent_base.py          — базовый класс (HF first → Gemini)
  │   ├── agent_factory.py       — динамические специалисты
  │   ├── orchestrator.py        — 5 агентов + pipeline
  │   ├── registry.py            — реестр агентов
  │   └── music_db.py            — проверенная музыка для массажа
  ├── questionnaire.py           — модель анкеты (data-driven)
  ├── music_player.py            — IA-музыка + плейлисты
  └── network.py                 — DNS patch
```

---

## 🚀 Быстрый старт

```bash
git clone https://github.com/dizel0110/ai_prophet
cd ai_prophet
cp .env.example .env  # заполнить TELEGRAM_TOKEN, GEMINI_API_KEY, HF_TOKEN
pip install -r requirements.txt
python main.py
```

Система требует ffmpeg (для аудио и yt-dlp).

---

## 🌱 Философия

AI Prophet — это **проводник**, а не продукт. Массаж, музыка, поиск — всё это возможности одного ИИ-агента, который соединяет человека с нужным знанием.

Проект растёт снизу вверх: от конкретных семейных задач к универсальной платформе. Если ты видишь в этом потенциал для своей сферы — присоединяйся.

---

## 🚀 CI/CD

- `main` → авто-деплой на Hugging Face Spaces (через GitHub Actions)
- Render.com подхватывает main через Git-интеграцию
- Ветки → force-push на HF Spaces (без PR gate)

---

## ⚖️ Юридическая информация и Лицензия

Этот проект является интеллектуальной собственностью **dizel0110**. Уникальные алгоритмы переключения моделей (Fallback Engine) и концепция "AI Prophet" защищены лицензией **Apache 2.0**.

*   **Авторское право**: © 2026 dizel0110.
*   **Использование**: Разрешено для личного и образовательного использования при сохранении ссылок на оригинал.
*   **Коммерция**: Для интеграции в коммерческие продукты, пожалуйста, свяжитесь с автором.

---

*Являя суть вещей через код. 2026.*
