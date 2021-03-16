import requests
from time import sleep
from tqdm import tqdm
from datetime import datetime
import json


def validate_user_id(user_id, token):
    """
    эта функция проверяет, есть ли user_id в базе ВК, True - если есть, False - если нет
    и ещё она подменит screen_name на id если ввести именно screen_name
    """

    correct_id = user_id

    params = {
        'user_ids': user_id,
        'access_token': token,
        'v': '5.126'
    }
    res = requests.get('https://api.vk.com/method/users.get', params=params)
    # print(res.json())
    if "error" in res.json():  # ошибка id - неправильный id, такого пользователя нету ВК
        print(res.json()['error']['error_msg'], "- такого пользователя нет в ВК, продолжить нельзя")
        return False, correct_id

    print('Успешно введён id пользователя')

    try:
        int(user_id)
        return True, correct_id

    except ValueError:
        correct_id = res.json()['response'][0]['id']
        return True, correct_id


def download_vk_photos(user_id, token, album_id="profile"):
    """
    скачивает фотки пользователя user_id
    :return словарь типа ключ - количество лайков фотки: значение - ссылка на неё
    """
    max_photos_count = int(input("Введите, сколько фоточек хотите скачать: "))

    params = {
        'owner_id': user_id,
        'access_token': token,
        'v': '5.126',
        'album_id': album_id,
        'photo_sizes': True,
        'count': max_photos_count,
        'extended': True
    }

    response = requests.get('https://api.vk.com/method/photos.get', params=params)
    # print(response.status_code)
    # print(response.json())

    if "error" in response.json():  # ошибка что пользователь закрыл фотки или удалён
        print(response.json()['error']['error_msg'])

    else:
        result = response.json()['response']['items']
        # print(response.json())
        print('количество фоточек в альбоме', response.json()['response']['count'])
        # print(result)

        links_dict = {}
        for photo in result:
            like = photo['likes']['count']
            link = photo['sizes'][-1]['url']
            # print('количество доступных размеров', len(photo['sizes']))
            # print('количество лайков фоточки', like)
            # print()

            if link not in links_dict.values():  # чтобы две одинаковые фотки не заливать
                if like not in links_dict.keys():
                    links_dict[like] = link
                else:
                    # print(photo['date'])
                    normal_date = datetime.utcfromtimestamp(int(photo["date"])).strftime('%Y-%m-%d_%H-%M-%S')
                    # print(normal_date)
                    links_dict[f'{like}_{str(normal_date)}'] = link

        with open('output_data.json', 'w') as output_file:  # json dumper - как по условию
            output_json = {user_id: {album_id: links_dict}}
            json.dump(output_json, output_file)
            print(f'Данные сохранены также в файл output_data.json ')

        return links_dict


def yandex_uploader(user_id: str, photos_list: dict, album_id="profile"):
    """
    вводим токен яндекса
    создаём папку с именем id пользователя из ВК
    создаём альбом с именем названия альбома (profile, wall)
    закачиваем в этот альбом все файлы из словаря photos_list
    сохраняем данные в выходной файл в формате json
    """
    if photos_list:

        ya_token = input("Введите токен яндекса: ")

        folder_name = f'user_{user_id}'  # создаём папку user_userid
        response = requests.put('https://cloud-api.yandex.net/v1/disk/resources',
                                params={'path': folder_name},
                                headers={'Authorization': f'OAuth {ya_token}'})
        if response.status_code in [201, 409]:  # если папка создалась (201) или уже есть (409)
            album_folder_name = f'user_{user_id}/{album_id}'  # создаём внутри папку альбома
            response = requests.put('https://cloud-api.yandex.net/v1/disk/resources',
                                    params={'path': album_folder_name},
                                    headers={'Authorization': f'OAuth {ya_token}'})

            if response.status_code in [201, 409]:  # если она создалась, тогда загружаем

                files = requests.get('https://cloud-api.yandex.net/v1/disk/resources/',
                                     params={'path': f'user_{user_id}/{album_id}'},
                                     headers={'Authorization': f'OAuth {ya_token}'})

                # print(files.json())
                names = []  # проверка папки на имена файлов, чтобы потом не добавлять такие же
                if "error" not in files.json():
                    number = files.json()['_embedded']['items']
                    # print(len(number))
                    for each in number:
                        names.append(each['name'])
                # print(names)

                print("Начинаем загрузку")
                i = 0  # счетчик количества повторяющихся файлов
                for key, value in tqdm(photos_list.items()):

                    if str(key) not in names:
                        requests.post('https://cloud-api.yandex.net/v1/disk/resources/upload',
                                      params={'path': f'{album_folder_name}/{key}', 'url': value},
                                      headers={'Authorization': f'OAuth {ya_token}'})
                        sleep(1)

                    else:
                        print('такой уже есть')
                        i += 1

                if i == 0:
                    print("Загрузка завершена")
                else:
                    print(f'Загрузка завершена, {i} не загружено, так как они уже есть')

                with open('current_time_log.txt', "a+", encoding='utf-8') as f:  # лог txt с дозаписью
                    line = f'_user_id={user_id}_album={album_id}_____загружено_{len(photos_list) - i}_фоток\n'
                    f.write(str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + line))
                    print('log_file updated')

            else:  # это если она не создалась, например уже есть (повторно хотим заслать альбом)
                print(response.json()['message'])

        else:  # а это если ошибка на уровне целого пользователя
            print(response.json()['message'])

    else:  # а это если с пользователем ВК всё было ок, но у него нету фоточек
        print("У пользователя нет фоток или он закрытый")


def uploader():
    with open("token_vk.txt") as f:
        # f.readline()  # добавить эту строчку чтобы считать токен коровина, убрать чтобы считать мою
        token = f.read().split()[0]

    # token = "вставьте ваш токен ВК сюда"

    user_id = input("Введите id пользователя, откуда будем скачивать фотографии: ")

    validate_user, user_id = validate_user_id(user_id, token)

    if validate_user:
        user_photos = download_vk_photos(user_id, token)

        # if user_photos:
        #     for key, value in user_photos.items():
        #         print(key, value)

        yandex_uploader(user_id, user_photos)


if __name__ == "__main__":
    uploader()
