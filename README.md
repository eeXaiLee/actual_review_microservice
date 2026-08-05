# Проект для парсинга отзывов

Сервис для сбора отзывов с Яндекс.Карт, 2GIS и VL.RU.

**Ссылки:**
- Swagger (документация API): http://185.104.113.137:8000/swagger/
- Админ-панель: http://185.104.113.137:8000/admin

## Переменные окружения

Перед первым запуском скопируйте `.env.example` в `.env` и заполните реальными значениями — без файла `.env` (точнее, без `SECRET_KEY` в нём) проект не запустится вообще:

```
cp .env.example .env
```

- `SECRET_KEY` — обязателен, без значения по умолчанию. Сгенерировать новый: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
- `DEBUG` — `True`/`False`.
- `ALLOWED_HOSTS` — домены/IP через запятую, без пробелов.
- `CELERY_BROKER_URL` — адрес Redis для Celery (`redis://redis:6379/0` в docker-compose, `redis://localhost:6379/0` для локального запуска).
- `TWOGIS_API_KEY` — ключ 2GIS Public API, без него парсинг 2GIS не работает.

При запуске через `docker compose up` переменные подхватываются из `.env` автоматически (`env_file:` в `docker-compose.yml`).

## Добавление новой организации:

1.	Заходим в админку -> организации
2.	Добавляем данные, создаем ветку (лучше всего на каждый адресс организации делать отдельную ветку)
 ![image](https://github.com/user-attachments/assets/08bafca2-e0c0-4ff3-b360-02fbba959e8f)

3.	Заполняем данные ветки.
 ![image](https://github.com/user-attachments/assets/d274454b-b7e2-43ce-92e4-1ccf0ba6618d)

Ссылка на яндекс должна быть полной, чтоб при переходе по ней открывалось аналогичное окно.
![image](https://github.com/user-attachments/assets/7ea7db1f-b500-483e-a98d-55b531bf7b7c)

Ссылка на гугл должна быть полной, чтоб при переходе по ней открывалось аналогичное окно.
![image](https://github.com/user-attachments/assets/7216e71a-e4ab-4f80-b671-966d82fefe56)
 
Ссылки на 2gis и vlru должны быть аналогичными следующим:
https://2gis.ru/vladivostok/firm/70000001062587396
https://www.vl.ru/art-mesh

так же нужно из страницы vl.ru вытащить company_id и вставить в поле Vlru org id
 ![image](https://github.com/user-attachments/assets/cbd06857-e30b-42f2-945c-0701383c74c4)

4.	При сохранении новой ветки так же включается парсинг в асинхронном режиме, данные заполнятся через пару минут. Парсинг всех веток происходит каждое воскресенье в 11 утра.

После парсинга ветки заполняются успешно взятыми данными и создаются отзывы:
 ![image](https://github.com/user-attachments/assets/be605876-527f-4364-87f1-496cffee688e)

## Получение отзывов

5.	Для получения отзывов по ip создаем объект branch ip mapping:
 ![image](https://github.com/user-attachments/assets/d09da0e5-80f2-4b2c-a767-56bc6ba69c97)

6.	Документация по получению данных через API: http://185.104.113.137:8000/swagger/

**Эндпоинты:**
- `GET /api/common/reviews?branch_id=<id>` — отзывы по ID филиала
- `GET /api/common/reviews_by_ip` — отзывы по IP клиента (заголовок X-Forwarded-For или REMOTE_ADDR)
- `GET /api/common/get_videos_by_ip` — видео по IP клиента

**Структура ответа:**
- **branch** (или **branches** для get_reviews_by_ip) — данные филиала: средние оценки и количество отзывов с каждого провайдера (google, yandex, twogis, vlru). Если оценку не удалось определить — будет -1.
- **provider_reviews_count** — количество отзывов по провайдерам в БД.
- **reviews** — массив отзывов. Поле `photos` — ссылки на картинки через запятую.

## Фильтры и параметры в запросе на получение отзывов

- `min_rating` — минимальный рейтинг отзыва, по умолчанию `4`. Чтобы получить вообще все отзывы, включая низкие оценки, передайте `min_rating=1`.
- `offset`, `limit` — пагинация (работают, только если не задан `providers`).
- `sort_photos=true` — сначала показывать отзывы с фото.
- `providers` — нужные площадки через запятую, например `providers=yandex,vlru`.
- `only_providers=true` — показывать только площадки из `providers`, без остальных.
- `count_<provider>` — лимит отзывов для конкретной площадки, например `count_yandex=5`.
- `filters` / `filters_<provider>` — фильтр по полям отзыва. Общий `filters` действует, только если `providers` не задан; `filters_<provider>` — для конкретной площадки внутри `providers`.

Разрешённые поля для фильтра: `author`, `avatar`, `video`, `photos`, `published_date`, `rating`, `content`, `provider`, `review_url`.
Разрешённые операторы: `exact` (по умолчанию, можно не указывать), `gt`, `lt`, `gte`, `lte`, `in`, `isnull`, `icontains`. Фильтр по любому другому полю (в том числе по связанным моделям) будет отклонён с ошибкой 400.

Примеры фильтров (фильтр в запросе → какой результат будет). Несколько условий соединяются через "&":

    - author=test
    - author!=test
    - rating__gt=4 → rating > 4
    - rating__lt=5 → rating < 5
    - author__icontains=test → test содержится в author
    - !author__icontains=test → test не содержится в author
    - rating__in=1,2,3 → rating в 1,2,3
    - !rating__in=1,2,3 → rating не в 1,2,3
    - avatar__isnull=true → avatar не заполнен
    - avatar__isnull=false → avatar заполнен

Примеры запросов:

- Все отзывы филиала, включая низкие оценки:
  - `GET /api/common/reviews?branch_id=<id>&min_rating=1&limit=50&offset=0`

- Взять только Яндекс и VL.ru (Яндекс ограничить одним отзывом):
  - `GET /api/common/reviews?branch_id=<id>&providers=yandex,vlru&count_yandex=1&only_providers=true`

- Фильтр по конкретной площадке:
  - `GET /api/common/reviews?branch_id=<id>&providers=yandex&filters_yandex=rating__gt=4&only_providers=true`

## Видео

Автоматический парсинг видео из YouTube/VK-плейлистов из проекта убран (модуль удалён при рефакторинге структуры). Модели `Playlist`/`Video` и получение уже сохранённых видео по IP по-прежнему работают.

## Получение видео 

Создаём Playlist IP Mappings в админке и получаем данные на эндпоинте `GET /api/common/get_videos_by_ip` (подробнее в Swagger).
Ответ содержит: `ip`, `playlists`, `provider_videos_count`, `videos`.

![image](https://github.com/user-attachments/assets/1d1f9316-d82b-4f7b-98b9-a1201b28280b)


## Ручной парсинг

Если при создании был неудачный парсинг или понадобилось запарсить вручную. Можно зайти в ветку и нажать на кнопки парсинга:

![image](https://github.com/user-attachments/assets/5ca2a34d-4d89-48a2-a3f2-7cc2c592c237)

![image](https://github.com/user-attachments/assets/eae6e6a4-3cc9-43aa-8852-a84023af8a39)


