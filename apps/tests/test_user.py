import pytest
from django.test import TransactionTestCase
from mixer.backend.django import mixer
from rest_framework import status
from rest_framework.test import RequestsClient, APITestCase

from apps.client.models import Client
from apps.user.models import User, UserToken
from apps.user.serializers import WechatUserSerializer

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
        response = self.client.get(url=url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(f'\nTestCase: {url} \nresponse: {response.json()}')

    def test_mina_login(self):
        code = '023MOF8I1OMzX10y4j6I1zCN8I1MOF8j'
        url = f'http://127.0.0.1:10001/api/mina/login?cid={self.cid}&code={code}'
        response = self.client.get(url)
        error_msg = response.json()['m']
        self.assertEqual(error_msg.split(':')[0], 'invalid appid hint')
        print(f'\nTestCase: {url} \nresponse: {response.json()}')

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
        # fields = [i for i in WechatUserSerializer().fields]
        # model_fields = [f.name for f in User._meta.get_fields()]
        # print(fields)
        # print(model_fields)
        response = self.client.post(url=url, data=data)
        print(response.text)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(f'\nTestCase: {url} \nresponse: {response.json()}')
