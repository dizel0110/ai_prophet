# ⚙️ Настройка Виртуального Окружения для Проекта

## 🚀 Автоматическая Активация при Открытии Проекта

VS Code автоматически активирует виртуальное окружение, если правильно настроить проект.

---

## 📁 Вариант 1: `.vscode/settings.json` (Рекомендуется)

Этот файл уже создан в проекте. Он указывает VS Code использовать конкретный интерпретатор:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}\\venv\\Scripts\\python.exe"
}
```

**Как работает:**
- При открытии папки проекта VS Code читает `.vscode/settings.json`
- Автоматически выбирает указанный Python-интерпретатор
- Терминал активирует окружение при запуске

**Для разных менеджеров пакетов:**

| Менеджер | Путь к интерпретатору |
|----------|----------------------|
| **venv** | `${workspaceFolder}\\venv\\Scripts\\python.exe` |
| **uv** | `${workspaceFolder}\\.venv\\Scripts\\python.exe` |
| **poetry** | `${workspaceFolder}\\.venv\\Scripts\\python.exe` |
| **conda** | `${env:CONDA_PREFIX}\\python.exe` |
| **django (venv)** | `${workspaceFolder}\\venv\\Scripts\\python.exe` |

---

## 🔧 Вариант 2: Ручной Выбор (Если Auto Не Работает)

1. Открой проект в VS Code
2. Нажми `Ctrl+Shift+P` → введи **"Python: Select Interpreter"**
3. Выбери интерпретатор из списка (должен содержать `venv`)
4. VS Code запомнит выбор для этого проекта

---

## 📝 Проверка Активации

После открытия проекта:

1. Открой терминал в VS Code (`Ctrl+``)
2. Введи:
   ```bash
   where python
   ```
3. Должен увидеть путь к `venv\Scripts\python.exe`, а не системный Python

Или:
```bash
python -c "import sys; print(sys.executable)"
```

---

## 🔄 Для Других Проектов

Каждый проект может иметь свой `.vscode/settings.json` с уникальным путём:

**Пример для проекта с uv:**
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe"
}
```

**Пример для Django проекта:**
```json
{
    "python.defaultInterpreterPath": "/home/user/myproject/venv/bin/python"
}
```

---

## ⚠️ Если Окружение Не Активируется

1. **Проверь, что venv существует:**
   ```bash
   ls venv\Scripts\python.exe
   ```

2. **Пересоздай venv:**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Включи авто-активацию в настройках VS Code:**
   - `Ctrl+,` → найди "Python Terminal Activate"
   - Убедись, что `"python.terminal.activateEnvironment": true`

4. **Перезагрузи VS Code:**
   - `Ctrl+Shift+P` → **"Developer: Reload Window"**

---

## 🎯 Текущая Конфигурация Этого Проекта

Файл: `.vscode/settings.json`

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}\\venv\\Scripts\\python.exe",
    "python.terminal.activateEnvironment": true
}
```

**Статус:** ✅ Настроено на `venv`

---

---

## 🌍 Деплой на Hugging Face Spaces

Для корректной работы на Hugging Face Spaces проект содержит:
1.  **requirements.txt**: Все Python-библиотеки.
2.  **packages.txt**: Системные зависимости (ffmpeg, dnsutils).
3.  **Dockerfile**: Если вы используете Docker-инстанс.

### 🎧 Установка FFMPEG (Критично)

Без `ffmpeg` бот не сможет:
- Скачивать музыку (через yt-dlp).
- Распознавать голосовые сообщения.

**Локально (Windows):**
1. Скачай [ffmpeg-release-essentials.zip](https://www.gyan.dev/ffmpeg/builds/).
2. Распакуй и добавь папку `bin` в переменную окружения **PATH**.
3. Проверь командой в терминале: `ffmpeg -version`.

**Hugging Face Spaces:**
- Устанавливается автоматически через `packages.txt`.

---

## 📚 Дополнительные Настройки (Опционально)

Для улучшенной разработки добавь в `.vscode/settings.json`:

```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    }
}
```
