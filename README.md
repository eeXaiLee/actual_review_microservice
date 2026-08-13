# Проект для парсинга отзывов и видео

Сервис для сбора отзывов с Яндекс.Карт, 2GIS и VL.RU, а также видео из YouTube-плейлистов.

**Ссылки:**
- Swagger (документация API): https://v3212274.hosted-by-vdsina.ru/swagger/
- Админ-панель: https://v3212274.hosted-by-vdsina.ru/admin

## Переменные окружения

Перед первым запуском скопируйте `.env.example` в `.env` и заполните реальными значениями — без файла `.env` (точнее, без `SECRET_KEY` в нём) проект не запустится вообще:

```
cp .env.example .env
```

- `SECRET_KEY` — обязателен, без значения по умолчанию. Сгенерировать новый: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
- `DEBUG` — `True`/`False`.
- `ALLOWED_HOSTS` — домены/IP через запятую, без пробелов.
- `CELERY_BROKER_URL` — адрес Redis для Celery (`redis://redis:6379/0` в docker-compose, `redis://localhost:6379/0` для локального запуска).
- `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` — обязательны, без значений по умолчанию. `POSTGRES_HOST`/`POSTGRES_PORT` по умолчанию рассчитаны на docker-compose (`postgres`/`5432`), для запуска вне docker-compose задайте `POSTGRES_HOST=localhost`.
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

4.	При сохранении новой ветки так же включается парсинг в асинхронном режиме, данные заполнятся через пару минут. Парсинг всех веток происходит каждое воскресенье в 6 утра по Москве.

После парсинга ветки заполняются успешно взятыми данными и создаются отзывы:
 ![image](https://github.com/user-attachments/assets/be605876-527f-4364-87f1-496cffee688e)

## Получение отзывов

5.	Доступ к API даётся по JWT-токену. Создаём клиента:
	- в админке создаём пользователя (Users) с логином/паролем для клиента;
	- создаём объект `ApiClient`, привязываем к нему этого пользователя и организацию, отзывы которой клиенту можно видеть.
6.	Клиент получает токен: `POST /api/common/token` с телом `{"username": "...", "password": "..."}` → `{"access": "...", "refresh": "..."}`. Дальше каждый запрос к API отзывов идёт с заголовком `Authorization: Bearer <access>`. Токен `access` живёт 12 часов, `refresh` — 30 дней (`POST /api/common/token/refresh` с `{"refresh": "..."}` → новый `access`).
7.	Документация по получению данных через API: https://v3212274.hosted-by-vdsina.ru/swagger/

**Эндпоинты (везде нужен заголовок `Authorization: Bearer <access>`):**
- `POST /api/common/token` — получить токен по логину/паролю
- `POST /api/common/token/refresh` — обновить `access` по `refresh`
- `GET /api/common/reviews?branch_id=<id>` — отзывы по ID филиала (403, если филиал принадлежит другой организации)
- `GET /api/common/organization_reviews` — отзывы по всем филиалам организации клиента

**Структура ответа:**
- **branch** (или **branches** для organization_reviews) — данные филиала: `organization` вложенным объектом (`id`, `name`, `inn`) и `providers` — статистика по каждой площадке (`yandex`, `2gis`, `vlru`): `url`, `parse_date`, `review_count`/`review_avg` (по всем отзывам, сохранённым в базе, без учёта фильтров) и `review_count_filtered`/`review_avg_filtered` (с учётом фильтров текущего запроса).
- **reviews** — массив отзывов с учётом всех фильтров, выборки и сортировки. Поле `photos` — массив ссылок на картинки, `rating` — число.
- **offset**, **limit** — текущие параметры пагинации.

## Фильтры и параметры в запросе на получение отзывов

- `min_rating` — минимальный рейтинг отзыва, по умолчанию `4`. Чтобы получить вообще все отзывы, включая низкие оценки, передайте `min_rating=1`.
- `providers` — нужные площадки через запятую, например `providers=yandex,vlru`. Если не задано — возвращаются отзывы со всех площадок филиала.
- `has_photos` — `true` — только отзывы с фото, `false` — только без фото.
- `author` — поиск по автору (частичное совпадение, без учёта регистра).
- `limit` — максимальное количество отзывов в ответе. Если `providers` не задан, отзывы выбираются из объединённой выборки по всем площадкам филиала.
- `pick` — какие именно `limit` отзывов взять: `latest` — самые новые, `earliest` — самые старые, `random` — случайные. Без этого параметра действует обычная постраничная выдача через `offset`.
- `sort` — как расположить отобранные отзывы для показа: `newest` (по умолчанию), `oldest` или `photos_first`.
- `offset` — смещение для постраничной выдачи. Не показывается в форме Swagger, но принимается как обычный query-параметр.
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

- 10 случайных отзывов из всех площадок филиала:
  - `GET /api/common/reviews?branch_id=<id>&limit=10&pick=random`

## Видео

Парсинг YouTube-плейлистов работает (VK — нет, парсер под него убран при рефакторинге и не восстановлен).

Для парсинга YouTube нужен ключ `YOUTUBE_API_KEY` (YouTube Data API v3, берётся в Google Cloud Console) — без него парсинг вернёт ошибку в лог и ничего не сохранит.

Добавление плейлиста:
1.	Заходим в админку -> Playlists -> добавляем плейлист: выбираем `organization` (иначе плейлист не попадёт в выдачу ни одному клиенту), вставляем ссылку на плейлист вида `https://www.youtube.com/playlist?list=...`, `provider` = `youtube`.
2.	Сохраняем и на странице плейлиста нажимаем «Парсинг ютуб» — запускается асинхронный парсинг, видео появятся через некоторое время.

Получение видео (тот же JWT-токен, что и для отзывов — см. раздел «Получение отзывов» выше):
- `GET /api/common/videos?playlist_id=<id>` — видео по ID плейлиста (403, если плейлист принадлежит другой организации). Ответ содержит: `playlist`, `provider_videos_count`, `videos`.
- `GET /api/common/organization_videos` — видео по всем плейлистам организации клиента. Ответ содержит: `playlists`, `provider_videos_count`, `videos`.


## Ручной парсинг

Если при создании был неудачный парсинг или понадобилось запарсить вручную. Можно зайти в ветку и нажать на кнопки парсинга:

![image](https://github.com/user-attachments/assets/5ca2a34d-4d89-48a2-a3f2-7cc2c592c237)

![image](https://github.com/user-attachments/assets/eae6e6a4-3cc9-43aa-8852-a84023af8a39)


