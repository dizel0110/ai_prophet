# MCP Guide — AI Prophet

## Что такое MCP?

**Model Context Protocol** — стандарт подключения внешних инструментов к AI-агентам (как opencode, так и бот). Позволяет агенту вызывать функции в реальном мире: открывать браузер, читать файлы, ходить в базу данных.

## Установка Playwright MCP

Playwright MCP даёт агенту браузер: открывать сайты, делать скриншоты, заполнять формы, кликать.

### 1. Установка зависимостей

```bash
# Из корня проекта
npm install @playwright/mcp
npx playwright install chromium
```

### 2. Настройка opencode

Файл: `~/.config/opencode/opencode.jsonc`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcpServers": {
    "playwright": {
      "command": "node",
      "args": [
        "node_modules/@playwright/mcp/cli.js",
        "--headless"
      ]
    }
  }
}
```

**Важно**: `args` использует относительный путь `node_modules/@playwright/mcp/cli.js` — команда должна запускаться из корня проекта (где установлен пакет).

### 3. Проверка

После перезапуска opencode MCP-сервер запустится автоматически. Агент получит новые инструменты:

- `browser_navigate` — открыть URL
- `browser_snapshot` — получить HTML/текст страницы
- `browser_screenshot` — скриншот
- `browser_click` — клик по элементу
- `browser_fill` — заполнить поле
- `browser_select` — выбор из списка

### 4. Для бота (TODO)

Интеграция Playwright в aiogram-бота добавит команды:

- `/browse <url>` — открыть страницу, вернуть текст
- `/screenshot <url>` — скриншот сайта
- `/check <url>` — проверка доступности сайта

Требуется установка `playwright` для Python:

```bash
pip install playwright
playwright install chromium
```

## Чем Playwright лучше webfetch

| Возможность | webfetch | Playwright |
|-------------|----------|------------|
| GET-запрос | ✅ | ✅ |
| JavaScript-рендер | ❌ | ✅ |
| Клики/формы | ❌ | ✅ |
| Скриншоты | ❌ | ✅ |
| Авторизация | ❌ | ✅ |
| Ожидание контента | ❌ | ✅ |
| Работа с iframe | ❌ | ✅ |

## ngrok — HTTPS для локального тестирования

Telegram Mini App требует HTTPS. На HF Spaces это работает автоматически. Локально — нужен туннель.

### Установка

```bash
npm install -g ngrok
```

### Запуск

```bash
# Терминал 1: бот
python main.py

# Терминал 2: ngrok туннель (новое окно)
ngrok http 7860
```

ngrok покажет HTTPS-ссылку вида `https://xxxx-xx-xx-xx-xx.ngrok-free.app`.

### Настройка Mini App URL

В `.env` укажи:

```
MINI_APP_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app
```

Теперь Telegram сможет открыть Mini App через HTTPS-туннель.

### Альтернатива без установки

**localhost.run** — SSH-туннель, не требует установки:

```bash
ssh -R 80:localhost:7860 localhost.run
```
