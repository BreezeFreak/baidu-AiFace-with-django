import pytest
from django.test import TransactionTestCase
from mixer.backend.django import mixer
from rest_framework import status
from rest_framework.test import RequestsClient

from apps.user.models import User, UserToken

pytestmark = pytest.mark.django_db


class UserTestCase(TransactionTestCase):

    def setUp(self):
        self.client = RequestsClient()
        user_token = mixer.blend(UserToken)
        self.token = user_token.token_string
        self.cid = user_token.user.client.id
        self.client.headers = {
            'X-TOKEN': self.token,
            'X-CID': str(self.cid)
        }

    def test_get_info(self):
        url = 'http://127.0.0.1:10001/api/user/getInfo/'
        return self.client.get(url=url)

    def test_mina_login(self):
        code = '023MOF8I1OMzX10y4j6I1zCN8I1MOF8j'
        url = f'http://127.0.0.1:10001/api/mina/login?cid={self.cid}&code={code}'
        return self.client.get(url=url)

    def test_mina_save_info(self):
        url = 'http://127.0.0.1:10001/api/mina/saveUserInfo/'
        user = mixer.blend(User)
        data = {
            'nickName': 'joe',  # user.name validate error: blank
            'avatarUrl': user.avatar,
            'gender': user.gender,
            'country': user.country,
            'province': user.province,
            'city': user.city
        }
        return self.client.post(url=url, data=data)

    def test_with_right_headers(self, test_status=status.HTTP_200_OK):
        response = self.test_get_info()
        self.assertEqual(response.status_code, test_status)
        print_short_cut(response)

        response = self.test_mina_login()
        error_msg = response.json()['m']
        self.assertRegex(error_msg, '^invalid appid hint')
        print_short_cut(response)

        response = self.test_mina_save_info()
        self.assertEqual(response.status_code, test_status)
        print_short_cut(response)

    def test_with_wrong_headers(self):
        self.client.headers = {
            'X-TOKEN': 'wrong_token',
            'X-CID': str(self.cid)
        }
        self.test_with_right_headers(test_status=status.HTTP_401_UNAUTHORIZED)


def print_short_cut(response):
    print(f'\nTestCase: {response.url} \nresponse: {response.json()}')
