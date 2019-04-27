import pytest
from django.test import TransactionTestCase
from django.urls import reverse
from mixer.backend.django import mixer
from rest_framework import status
from rest_framework.reverse import reverse as drf_reverse
from rest_framework.test import RequestsClient

from apps.user.models import User, UserToken
from apps.user import views

pytestmark = pytest.mark.django_db


def print_short_cut(response):
    print(f'\nTestCase: {response.url} '
          f'\nResponse: {response.json()}')


class UserTestCase(TransactionTestCase):

    def setUp(self):
        user_token = mixer.blend(UserToken)
        self.token = user_token.token_string
        self.cid = user_token.user.client.id

        self.client = RequestsClient()  # 这个对象虽然提供了一些东西，但是 url 需要 http://...
        self.client.headers = {
            'X-TOKEN': self.token,
            'X-CID': str(self.cid)
        }
        self.host = 'http://127.0.0.1:10001'

        user = mixer.blend(User)
        self.user_data = {
            'nickName': 'joe',  # default value: user.nick = '', which is not allowed
            'avatarUrl': user.avatar,
            'gender': user.gender,
            'country': user.country,
            'province': user.province,
            'city': user.city
        }

    # 3个可用的访问接口
    def test_get_info(self):
        # url = reverse(views.GetInfoView)
        url = self.host + '/api/user/getInfo/'
        return self.client.get(url=url)

    def test_mina_login(self):
        code = '023MOF8I1OMzX10y4j6I1zCN8I1MOF8j'
        url = self.host + f'/api/mina/login?cid={self.cid}&code={code}'
        return self.client.get(url=url)

    def test_mina_save_info(self):
        url = self.host + '/api/mina/saveUserInfo/'
        return self.client.post(url=url, data=self.user_data)

    # 给 test_mina_save_info 传递错误的参数
    def test_saving_wrong_user_data(self):
        user = mixer.blend(User)
        self.user_data = {
            'nickName': '',  # blank
            # 'avatarUrl': user.avatar,  # missing
            'gender': str(user.gender),  # not int
            'country': user.country,
            # 'province': user.province, # missing
            'city': user.city
        }
        response = self.test_mina_save_info()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['c'], -1)
        print_short_cut(response)

    def test_regular(self, test_status=status.HTTP_200_OK, code=0):
        """
        正常情况下的测试
        :param test_status: 返回的 response 体，http 解析得到的状态码
        :param code:        返回的 {'c': 0, 'm': '', 'd': ''}, c 应该为 code 的值
        :return:
        """
        response = self.test_get_info()
        self.assertEqual(response.status_code, test_status)
        self.assertEqual(response.json()['c'], code)
        print_short_cut(response)

        response = self.test_mina_login()
        error_msg = response.json()['m']
        self.assertRegex(error_msg, '^invalid appid hint')
        self.assertEqual(response.json()['c'], -1)
        print_short_cut(response)

        response = self.test_mina_save_info()
        self.assertEqual(response.status_code, test_status)
        self.assertEqual(response.json()['c'], code)
        print_short_cut(response)

    def test_with_wrong_headers(self):
        self.client.headers = {
            'X-TOKEN': 'wrong_token',
            'X-CID': '-1'
        }
        self.test_regular(test_status=status.HTTP_401_UNAUTHORIZED, code=-1)

    def test_without_headers(self):
        self.client.headers = {}
        self.test_regular(test_status=status.HTTP_401_UNAUTHORIZED, code=-1)
