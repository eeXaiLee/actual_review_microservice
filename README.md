# Проект для парсинга отзывов

Сервис для сбора отзывов с Яндекс.Карт, 2GIS, VL.RU и видео из плейлистов YouTube и VK.

**Ссылки:**
- Swagger (документация API): http://185.104.113.137:8000/swagger/
- Админ-панель: http://185.104.113.137:8000/admin

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
- `GET /api/common/get_reviews/?branch_id=<id>` — отзывы по ID филиала
- `GET /api/common/get_reviews_by_ip` — отзывы по IP клиента (заголовок X-Forwarded-For или REMOTE_ADDR)
- `GET /api/common/v2/reviews?branch_id=<id>` — отзывы v2 (рекомендуется)
- `GET /api/common/v2/reviews_by_ip` — отзывы v2 по IP (рекомендуется)
- `GET /api/common/get_videos_by_ip` — видео по IP клиента

**Структура ответа:**
- **branch** (или **branches** для get_reviews_by_ip) — данные филиала: средние оценки и количество отзывов с каждого провайдера (google, yandex, twogis, vlru). Если оценку не удалось определить — будет -1.
- **provider_reviews_count** — количество отзывов по провайдерам в БД.
- **reviews** — массив отзывов. Поле `photos` — ссылки на картинки через запятую.

## Фильтры и параметры в запросе на получения отзывов (v1)

Параметр "only_providers": True отвечает за то, что в результате будут только провайдеры из массива providers.

Фильтры пишутся в параметре "filters" элемента параметра "providers":

{

  "provider": "2gis",
  
  "count": 0,
  
  "filters": "avatar__isnull=false&rating__gt=4"
  
}

Примеры фильтров (фильтр в запросе → какой результат будет). Фильтры можно соединять конструкцией И через "&" между ними

    - author=test
    
    - author!=test
    
    - rating__gt=4 → rating > 4
    
    - rating__lt=5 → rating < 5
    
    - author__icontains=test → test in author
    
    - !author__icontains=test → not test in author
    
    - rating__in=1,2,3 → rating in 1,2,3
    
    - !rating__in=1,2,3 → not rating in 1,2,3
    
    - avatar__isnull=true → avatar = null
    
    - avatar__isnull=false → avatar != null

## Рекомендуемый формат параметров (v2)

В v2 можно передавать провайдеры как CSV и управлять лимитами/фильтрами без JSON.

Примеры:

- Получить отзывы по филиалу (последние 50):
  - `GET /api/common/v2/reviews?branch_id=<id>&limit=50&offset=0`

- Взять только Яндекс и VL.ru (Яндекс ограничить одним отзывом):
  - `GET /api/common/v2/reviews?branch_id=<id>&providers=yandex,vlru&count_yandex=1&only_providers=true`

- Фильтры по провайдеру:
  - `GET /api/common/v2/reviews?branch_id=<id>&providers=yandex&filters_yandex=rating__gt=4&only_providers=true`

## Парсинг видео

создаем новый плейлист и добавляем ссылку на плейлист

![image](https://github.com/user-attachments/assets/fccf9c63-8a4f-4783-af7d-f50d406692e8)

для вк необходимо выбирать ссылки типа: https://vkvideo.ru/playlist/-157530610_10

(сейчас в вк парсится из плейлиста не более 10 видео, можно поменять)

для ютуба https://www.youtube.com/playlist?list=PLyIn--Pv43vK3HGN7uoH0N9A89zeYxdCn

сохраняем, после видио из плейлистов спарсятся.

## Получение видео 

Создаём Playlist IP Mappings в админке и получаем данные на эндпоинте `GET /api/common/get_videos_by_ip` (подробнее в Swagger).
Ответ содержит: `ip`, `playlists`, `provider_videos_count`, `videos`.

![image](https://github.com/user-attachments/assets/1d1f9316-d82b-4f7b-98b9-a1201b28280b)


## Ручной парсинг

Если при создании был неудачный парсинг или понадобилось запарсить вручную. Можно зайти в ветку и нажать на кнопки парсинга:

![image](https://github.com/user-attachments/assets/5ca2a34d-4d89-48a2-a3f2-7cc2c592c237)

![image](https://github.com/user-attachments/assets/eae6e6a4-3cc9-43aa-8852-a84023af8a39)


