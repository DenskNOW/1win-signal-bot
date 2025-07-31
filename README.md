# 1win Signal Bot

Бот для глемблинга с поддержкой сигналов, подписок и админ-панели. Работает с платформой 1win.

## 📦 Установка

```bash
pip install -r requirements.txt
```

## 🚀 Запуск

```bash
python bot.py
```

## 🌐 Railway деплой

1. Создай `.env` с переменными:
   - `TOKEN`
   - `PLATFORM_API_KEY`

2. Используй `Procfile`:
```
worker: python bot.py
```

3. Загрузи проект на GitHub и подключи в Railway.
