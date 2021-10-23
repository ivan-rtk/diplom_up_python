import sys
import vk_api
import json
import random
import pandas as pd
import Vkinder_inner as Inner
from Vkinder_service import JSONEncoder
from vk_api.longpoll import VkLongPoll, VkEventType
from random import randrange
from vk_api.exceptions import ApiError
import datetime
import psycopg2

conn = psycopg2.connect(dbname='vkinder_db', user='postgres',
                        password='postgres', host='localhost')
cursor = conn.cursor()

vk = vk_api.VkApi(token="<grouptoken>")
longpoll_vk_ = VkLongPoll(vk)

def write_msg(user_id, message_, attachment_=None):
    vk.method('messages.send',
              {'user_id': user_id,
               'message': message_,
               'random_id': randrange(10 ** 7),
               'attachment': attachment_})

def write_msg_result(user_id, message_, attachment_):
    vk.method('messages.send',
              {'user_id': user_id,
               'message': message_,
               'random_id': randrange(10 ** 7),
               'attachment': attachment_})

class VkClass:
    def __init__(self):
        self.info_fields = """bdate, sex, city, country, activities, 
        interests, music, movies, books, games, screen_name"""
        with open('token') as f:
            self.token_vk = f.read().strip()

        self.vk_session = vk_api.VkApi(token=self.token_vk,
                                       scope='friend, photo, '
                                             'offline, groups',
                                       api_version='5.131',
                                       app_id=7895057)
        self.vk_session._auth_token(reauth=True)
        self.vk = self.vk_session.get_api()
        self.user = self.vk.users.get()
        self.id = self.user[0]['id']
        self.vk_tools = vk_api.VkTools(self.vk_session)

        # Объявляем ключевые переменные для класса
        self.subj_info_dict = {}
        self.search_req = {}
        self.res_list = []
        self.dict_to_json = {}

        #print(f'\nПривет, {self.user[0]["first_name"]}')

    def get_subject_info(self, subject_id=None):
        """
        :param subject_id: uid пользователя,
            по умолчанию - id залогиненного юзера
        :return:
        """
        if not subject_id:
            subject_id = self.id

        self.subject_id_info = self.vk.users.get(user_ids=subject_id, fields=self.info_fields)

        self.subj_info_dict = Inner.build_subject_info(source_dict=self.subject_id_info)
        if type(self.subj_info_dict) == str:
            return self.subj_info_dict

        try:
            self.subj_friends = (self.vk.friends.get(user_id=self.subj_info_dict['id'])['items'])
            self.subj_info_dict['friends'] = self.subj_friends
        except Exception:
            print('error')
            sys.exit()

        self.subj_groups = (self.vk.groups.get(user_id=self.subj_info_dict['id'])['items'])
        self.subj_info_dict['groups'] = self.subj_groups

        return self.subj_info_dict

    def make_search_request(self, subject_id=None):

        if subject_id is None:
            subject_id = self.id

        self.get_subject_info(subject_id)

        self.target_sex = Inner.target_vk_sex(self.subj_info_dict['sex'])

        self.target_age = Inner.target_vk_age(self.subj_info_dict['age'])

        self.search_fields = "photo_id, verified, sex, bdate, city, " \
                             "country, photo_max_orig, has_mobile, " \
                             "relation, interests, music, movies, " \
                             "books, games"
        self.search_params = {
            'count': 30,
            'fields': self.search_fields,
            'sex': self.target_sex,
            'status': 6,
            'offset': random.randint(0, 24000),
            'age_from': self.target_age[0],
            'age_to': self.target_age[1],
            'has_photo': 1,
            'online': 1
        }
        if self.subj_info_dict['city_id']:
            self.search_params['city'] = self.subj_info_dict['city_id']

        self.search_req = (self.vk_tools.get_all
                           ('users.search', max_count=30,
                            values=self.search_params))

        return self.search_req

    def search_request_processing(self, subject_id=None):
        if subject_id == None:
            subject_id = self.id
        self.make_search_request(subject_id)
        self.tuples_list = []
        for person in self.search_req["items"]:
            print(f'\rОбработка информации: '
                  f'{self.search_req["items"].index(person) + 1} '
                  f'контакт из {len(self.search_req["items"])}',
                  end="", flush=True)
            try:
                self.books_rating = Inner.get_rating_from_items(
                    person, 'books', self.subj_info_dict
                )
                self.movies_rating = Inner.get_rating_from_items(
                    person, 'movies', self.subj_info_dict
                )
                self.music_rating = Inner.get_rating_from_items(
                    person, 'music', self.subj_info_dict
                )
                self.games_rating = Inner.get_rating_from_items(
                    person, 'games', self.subj_info_dict
                )
                self.interests_rating = Inner.get_rating_from_items(
                    person, 'interests', self.subj_info_dict
                )
                self.city_rating = Inner.get_rating_from_location(
                    person, 'city', self.subj_info_dict
                )
                self.friends_rating = Inner.get_rating_from_lists(
                    source=self.vk.friends.get(user_id=person['id']),
                    target=self.subj_info_dict['friends']
                )
                self.groups_rating = Inner.get_rating_from_lists(
                    source=self.vk.groups.get(user_id=person['id']),
                    target=self.subj_info_dict['groups']
                )
                self.f_rating = Inner.get_final_rating(
                    self.friends_rating, self.interests_rating,
                    self.city_rating, self.movies_rating,
                    self.music_rating, self.groups_rating,
                    self.books_rating, self.games_rating
                )
                self.tuples_list.append((person['id'], self.f_rating))
            except vk_api.exceptions.ApiError:
                pass
        self.t_df = pd.DataFrame(self.tuples_list,
                                 columns=['id', 'score'])
        self.res_list += (self.t_df.sort_values
                          ('score', ascending=False)
                          .head(30)['id'].tolist())
        return self.res_list

    def json_output(self, subject_id=None):
        if subject_id == None:
            subject_id = self.id

        self.search_request_processing(subject_id)  # Бывшая 176
        self.res_dict={}
        self.dict_to_json = {}
        j = 1
        for user_id in self.res_list:
            if j <= 3:
                vk_ = vk_api.VkApi(token=self.token_vk)
                select_find = f'SELECT count(*) FROM public."findVkinder" where "user"={self.id} and find_user={user_id}'
                cursor.execute(select_find)
                records = cursor.fetchone()[0]
                if records != 1:
                    try:
                        response = vk_.method('photos.get',
                                          {
                                              'access_token': self.token_vk,
                                              'v': '5.131',
                                              'owner_id': user_id,
                                              'album_id': 'profile',
                                              'count': 3,
                                              'extended': 1,
                                              'photo_sizes': -1,
                                          })

                    except ApiError:
                        continue
                    self.users_photos = []
                    self.res_dict[f'{user_id}']=[]
                    for i in range(10):
                        try:
                            self.users_photos.append(
                                [response['items'][i]['likes']['count'],
                                 response['items'][i]['id']])

                        except IndexError:
                            self.users_photos.append(['нет фото.'])
                    self.sorted_user_photo = Inner.sort_likes(self.users_photos)
                    self.res_dict[f'{user_id}'].append(self.sorted_user_photo)
                    j = j + 1;
                    try:
                        cursor.execute(f'Insert into public."findVkinder" VALUES ({self.id}, {user_id})')
                        conn.commit()
                    except:
                        print('error')
                        cursor.execute("ROLLBACK")
                        conn.commit()
                else:
                    continue
            else:
                break
        self.dict_to_json.update(self.res_dict)
        JSONEncoder().encode(self.dict_to_json)
        return self.dict_to_json

    def find_a_match(self, subject_id=None, json_dict=None,
                     file_name=None, db_name=None, to_file=False):
        if not subject_id:
            subject_id = self.id
        self.subject_id = subject_id
        if not file_name:
            time_save_file = str(datetime.datetime.today().strftime("%Y%m%d%H%M%S") )
            file_name = f'Vkinder_output_{self.subject_id}_{time_save_file}.json'
        self.file_name = file_name
        self.json_output(self.subject_id)
        if not json_dict:
            json_dict = self.dict_to_json
        self.json_dict = json_dict
        if to_file is True:
            with open(self.file_name, 'w',
                      encoding='utf8') as vkinder_json:
                data = self.json_dict
                json.dump(data, vkinder_json,
                          ensure_ascii=False, indent=2)
            print('\n File output is finished')
        return self.json_dict


if __name__ == '__main__':
    av = VkClass()
    print('find')
    for event in longpoll_vk_.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            if event.to_me:
                request = event.text
                if event.text == "привет":
                    write_msg(event.user_id, f"Хай, {event.user_id}")
                elif event.text == "поиск":
                    write_msg(event.user_id, f"Ожидайте, {event.user_id}")
                    result = av.find_a_match()
                    if len(result) > 0:
                        for i in result:
                            if i != '_id':
                                for j in result[i]:
                                    n = 1
                                    message = r'https://vk.com/id' + str(i)
                                    write_msg(event.user_id, message)
                                    while n <= len(j):
                                        a = n*(-1)
                                        attachment ='photo'+str(i)+'_'+str(j[a][1])
                                        n = n+1
                                        write_msg_result(event.user_id, 'Фото', attachment)
                    else:
                        write_msg(event.user_id, "Показали все что есть, поменяйте свои интересы и попытайтесь снова((")
                elif request == "пока":
                    write_msg(event.user_id, "Пока((")
                    break
                else:
                    write_msg(event.user_id, "Не поняла вашего ответа...")
