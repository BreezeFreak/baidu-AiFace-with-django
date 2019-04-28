import pytest
from django.test import TransactionTestCase, RequestFactory
from mixer.backend.django import mixer
from requests import Response
from rest_framework.test import RequestsClient

from apps.analysis.models import AnalysisResult
from apps.user.models import UserToken

pytestmark = pytest.mark.django_db


def print_short_cut(response):
    print(f'\n---- API Path: {response.request["PATH_INFO"]} '
          f'\n---- Response: {response.json()}')


class GetAnalysisResultTestCase(TransactionTestCase):

    def setUp(self):
        self.user_token = mixer.blend(UserToken)
        self.token = self.user_token.token_string
        self.cid = self.user_token.user.client.id
        # self.user = self.user_token.user

        self.analysis_result = mixer.blend(AnalysisResult, user=self.user_token.user)
        self.analysis_result = mixer.blend(AnalysisResult, user=self.user_token.user)
        self.analysis_result = mixer.blend(AnalysisResult, user=self.user_token.user)

        self.headers = {
            'HTTP_X_TOKEN': self.token,
            'HTTP_X_CID': str(self.cid)
        }

    def test_get_latest_result(self):
        path = '/api/analysis/result/latest/'
        return self.client.get(path=path, **self.headers)

    def test_get_result_by_id(self):
        path = f'/api/analysis/result/{self.analysis_result.id}/'
        return self.client.get(path=path, **self.headers)

    def test_regular(self, empty=False):
        response = self.test_get_latest_result()
        data = response.json().get('d')
        self.assertIsNot(bool(data), empty)
        print_short_cut(response)

        response = self.test_get_result_by_id()
        data = response.json().get('d')
        self.assertIsNot(bool(data), empty)
        print_short_cut(response)

    def test_with_wrong_headers(self):
        self.headers = {
            'HTTP_X_TOKEN': 'wrong_token',
            'HTTP_X_CID': '-1'
        }
        self.test_regular(empty=True)

    def test_without_headers(self):
        self.headers = {}
        self.test_regular(empty=True)

    def test_with_wrong_user(self):
        user_token = mixer.blend(UserToken)
        self.headers = {
            'HTTP_X_TOKEN': user_token.token_string,
            'HTTP_X_CID': str(user_token.user.client.id)
        }
        self.test_regular(empty=True)
