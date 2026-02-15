import requests
import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN:
    HF_TOKEN = HF_TOKEN.strip()

url = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "Привет! Ты работаешь?"}],
    "max_tokens": 10
}

print(f"--- Тест HF Роутера ---")
print(f"Токен (первые 10): {HF_TOKEN[:10]}...")
try:
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    print(f"Статус: {response.status_code}")
    if response.status_code == 200:
        print(f"Ответ: {response.json()['choices'][0]['message']['content']}")
    else:
        print(f"Ошибка: {response.text}")
except Exception as e:
    print(f"Исключение: {e}")
