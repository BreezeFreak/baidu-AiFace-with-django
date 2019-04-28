import json

import pytest
from django.http import HttpResponsePermanentRedirect
from mixer.backend.django import mixer
from rest_framework import status
from rest_framework.test import APITestCase

from apps.user.models import User, UserToken

pytestmark = pytest.mark.django_db


def print_short_cut(response):
    print(f'\n---- API Path: {response.request["PATH_INFO"]} '
          f'\n---- Response: {response.json()}')


class UserTestCase(APITestCase):
    """
    change the client as default, which cause many adjustment to fit in.
    finally done, fuck... save as a backup (the whole project is a backup)
    to compare with the drf one.
    """
    def setUp(self):
        user_token = mixer.blend(UserToken)
        self.token = user_token.token_string
        self.cid = user_token.user.client.id

        # self.client = RequestsClient()  # 这个对象虽然提供了一些东西，但是 path 需要 http://{host}...
        # self.client.headers = {}
        self.headers = {
            'HTTP_X_TOKEN': self.token,
            'HTTP_X_CID': str(self.cid),
            'content_type': 'application/json'
        }

        user = mixer.blend(User)
        self.user_data = {
            'nickName': 'not blank',
            'avatarUrl': user.avatar,
            'gender': user.gender,
            'country': 'not null',
            'province': 'not null',
            'city': 'not null'
        }

    # 3个可用的接口
    def test_get_info(self):
        # path = reverse(views.GetInfoView)
        path = '/api/user/getInfo/'
        return self.client.get(path=path, **self.headers)

    def test_mina_login(self):
        code = '023MOF8I1OMzX10y4j6I1zCN8I1MOF8j'
        path = f'/api/mina/login?cid={self.cid}&code={code}'
        return self.client.get(path=path, follow=True)  # where there is a HttpResponsePermanentRedirect object

    def test_mina_save_info(self):
        path = '/api/mina/saveUserInfo/'
        return self.client.post(path=path, data=json.dumps(self.user_data), **self.headers)

    # 正常情况下的测试
    def test_regular(self, test_status=status.HTTP_200_OK, code=0):
        response = self.test_get_info()
        print_short_cut(response)
        self.assertEqual(response.status_code, test_status)
        self.assertEqual(response.json()['c'], code)

        response = self.test_mina_login()
        print_short_cut(response)
        error_msg = response.json()['m']
        self.assertRegex(error_msg, '^invalid')
        self.assertEqual(response.json()['c'], -1)

        response = self.test_mina_save_info()
        print_short_cut(response)
        self.assertEqual(response.status_code, test_status)
        self.assertEqual(response.json()['c'], code)

    # 给 test_mina_save_info 传递错误的参数
    def test_saving_wrong_user_data(self):
        user = mixer.blend(User)
        self.user_data = {
            'nickName': '',  # blank
            # 'avatarpath': user.avatar,  # missing
            'gender': str(user.gender),  # not int
            'country': user.country,
            # 'province': user.province, # missing
            'city': user.city
        }
        response = self.test_mina_save_info()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['c'], -1)
        print_short_cut(response)

    # #以下 authentication 验证
    def test_with_wrong_headers(self):
        self.headers = {
            'HTTP_X_TOKEN': 'wrong_token',
            'HTTP_X_CID': '-1',
        }
        self.test_regular(test_status=status.HTTP_401_UNAUTHORIZED, code=-1)

    def test_without_headers(self):
        self.headers = {}
        self.test_regular(test_status=status.HTTP_401_UNAUTHORIZED, code=-1)
