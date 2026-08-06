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

**Структура ответа:**
- **branch** (или **branches** для get_reviews_by_ip) — данные филиала: средние оценки и количество отзывов с каждого провайдера (google, yandex, twogis, vlru). Если оценку не удалось определить — будет -1.
- **reviews** — массив отзывов с учётом всех фильтров и пагинации. Поле `photos` — ссылки на картинки через запятую.
- **total_filtered** — сколько всего отзывов подходит под текущий запрос (с учётом фильтров) — используйте, чтобы понять, есть ли следующая страница.
- **offset**, **limit** — текущие параметры пагинации.
- **provider_totals_unfiltered** — количество отзывов по провайдерам в БД, без учёта фильтров (просто общая статистика по площадкам, не связана с содержимым `reviews`).

## Фильтры и параметры в запросе на получение отзывов

- `min_rating` — минимальный рейтинг отзыва, по умолчанию `4`. Чтобы получить вообще все отзывы, включая низкие оценки, передайте `min_rating=1`.
- `offset`, `limit` — пагинация, работают всегда.
- `providers` — нужные площадки через запятую, например `providers=yandex,vlru`. Если не задано — возвращаются отзывы со всех площадок филиала.
- `has_photos` — `true` — только отзывы с фото, `false` — только без фото.
- `author` — поиск по автору (частичное совпадение, без учёта регистра).
- `sort` — `newest` (по умолчанию), `oldest` или `photos_first`.
- `filters` — продвинутый фильтр по полям отзыва для случаев, не покрытых параметрами выше (см. ниже).

Разрешённые поля для `filters`: `author`, `avatar`, `video`, `photos`, `published_date`, `rating`, `content`, `provider`, `review_url`.
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

- Только Яндекс и VL.ru, с фото, сначала новые:
  - `GET /api/common/reviews?branch_id=<id>&providers=yandex,vlru&has_photos=true&sort=newest`

- Поиск по автору с рейтингом выше 4 (через продвинутый фильтр):
  - `GET /api/common/reviews?branch_id=<id>&author=иван&filters=rating__gt=4`

## Видео (устаревшая функция)

Автоматический парсинг видео из YouTube/VK-плейлистов убран из проекта при рефакторинге. Модели `Playlist`/`Video` и уже накопленные ранее данные по ним по-прежнему доступны на чтение через `GET /api/common/get_videos_by_ip` (создайте Playlist IP Mapping в админке) — эндпоинт скрыт из Swagger как неподдерживаемый, но продолжает отдавать исторические данные. Ответ содержит: `ip`, `playlists`, `provider_videos_count`, `videos`.


## Ручной парсинг

Если при создании был неудачный парсинг или понадобилось запарсить вручную. Можно зайти в ветку и нажать на кнопки парсинга:

![image](https://github.com/user-attachments/assets/5ca2a34d-4d89-48a2-a3f2-7cc2c592c237)

![image](https://github.com/user-attachments/assets/eae6e6a4-3cc9-43aa-8852-a84023af8a39)


