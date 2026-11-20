# HTTP API

Адрес: http://127.0.0.1:5065. Cookie хранит подписанную сессию. Сначала GET /api/session, затем X-CSRF-Token во всех POST, PUT и DELETE. После входа и регистрации токен меняется; получите его снова. Коллекция Postman использует cookie jar и переменные коллекции.

Денежные значения ответа - целые копейки (*_cents). Цена входящей позиции unit_price - десятичная строка рублей с точностью до двух знаков. Номер заказа уникален. Изменение и удаление требуют актуальный version. При 409 перечитайте заказ. Повтор POST с тем же номером возвращает конфликт.

Фильтры: date_from, date_to (ISO, включительно, 1-366 дней), category_id, channel (web/phone/partner), status (new/paid/shipped/delivered/cancelled/returned). Пустой фильтр не ограничивает выборку. Без дат используется диапазон базы, ограниченный последними 366 днями. Реестр: page, 12 заказов на страницу.

Коды ответа: 200, 201; 400 - входные данные; 401 - нет сессии; 403 - CSRF/роль; 404 - нет записи; 409 - версия/уникальность; 413 - больше 1 МБ; 429 - частые попытки входа. Ошибка JSON: {"error":"описание"}.

## Сессия
GET /api/session
Доступ: Гость.

## Вход
POST /api/auth/login
Доступ: Гость.

```json
{
  "email": "admin@example.test",
  "password": "DemoPass2026!"
}
```

## Обновить CSRF после входа
GET /api/session
Доступ: Пользователь.

## Справочники
GET /api/dictionaries
Доступ: Пользователь.

## Статистика
GET /api/dashboard?date_from=2026-10-01&date_to=2026-11-05
Доступ: Пользователь.

## Реестр
GET /api/orders?page=1
Доступ: Пользователь.

## Создать заказ
POST /api/orders
Доступ: Администратор.

```json
{
  "number": "POSTMAN-001",
  "ordered_on": "2026-11-05",
  "customer": "Демо-покупатель",
  "channel": "web",
  "status": "delivered",
  "items": [
    {
      "product_id": 1,
      "quantity": 2,
      "unit_price": "1000.25"
    }
  ]
}
```

## Прочитать заказ
GET /api/orders/{{order_id}}
Доступ: Пользователь.

## Изменить заказ
PUT /api/orders/{{order_id}}
Доступ: Администратор.

```json
{
  "number": "POSTMAN-001",
  "ordered_on": "2026-11-05",
  "customer": "Демо-покупатель",
  "channel": "web",
  "status": "paid",
  "items": [
    {
      "product_id": 1,
      "quantity": 2,
      "unit_price": "1000.25"
    }
  ],
  "version": 1
}
```

## Удалить заказ
DELETE /api/orders/{{order_id}}?version=2
Доступ: Администратор.

## Аудит
GET /api/audit
Доступ: Администратор.

## CSV
GET /api/export.csv?date_from=2026-10-01&date_to=2026-11-05
Доступ: Пользователь.

## Регистрация
POST /api/auth/register
Доступ: Гость.

```json
{
  "name": "Демо-аналитик",
  "email": "new@example.test",
  "password": "DemoPass2026!"
}
```

## Выход
POST /api/auth/logout
Доступ: Пользователь.

```json
{}
```
