
# 🤖 Telegram Бот для учёта трат

Этот бот помогает двум пользователям вести совместный учёт расходов, быстро добавлять траты, пополнять баланс и отслеживать историю.

---

## 📦 Возможности

### 📥 Добавление трат и пополнений:
- **➕ Ввести вручную** — бот запросит сумму и добавит её.
- **⚡ Быстрые траты по кнопкам** — добавление суммы одним нажатием (настраивается).
- **💰 Добавить деньги** — пополнение общего баланса.

---

### 🧾 История операций:
- **🕘 История** — выбор количества отображаемых операций (`5 / 10 / 20 / 50`).
- **⬅️ / ➡️ Перелистывание страниц** — просмотр истории постранично.
- **📄 Все транзакции** — вывод всей истории одним списком.

---

### ⚙️ Управление кнопками:
- **⚙️ Управление кнопками** — настройка шаблонов трат:
  - ➕ Добавить новую кнопку с суммой.
  - ❌ Удалить ненужную кнопку.

---

### ⚠️ Администрирование:
- **🔄 Сбросить баланс** — установить баланс = 0.
- **🗑 Очистить историю** — удаление всех транзакций.
- **💱 Изменить валюту** — выбор символа валюты:
  - Стандартные: `₽, $, €, ₸, ₺, ₦, £, K`
  - ➕ Своя: можно ввести `USDT`, `💎`, `BTC` и т.д.

---

### 👥 Пользователи и безопасность:
- Только пользователи из `config.json` имеют доступ к боту.
- Каждое действие логируется с именем пользователя.

---

## 📁 Структура проекта

```
project/
├── bot.py              # основной код бота
├── data.json           # баланс, история и кнопки
├── config.json         # токен и авторизованные пользователи
├── requirements.txt    # зависимости
└── README.md           # описание (этот файл)
```

---

## 🚀 Запуск

1. Установите зависимости:

```
pip install -r requirements.txt
```

2. Заполните `config.json`:

```json
{
  "token": "ВАШ_ТОКЕН_БОТА",
  "authorized_users": [12345678, 87654321]
}
```

3. Запустите бота:

```
python bot.py
```

---
