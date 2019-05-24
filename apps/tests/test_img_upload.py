from io import BytesIO
from urllib import request

import pytest
import pathlib

from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from mixer.backend.django import mixer
from rest_framework.test import APITestCase

from apps.analysis.models import AnalysisResult
from apps.user.models import UserToken

pytestmark = pytest.mark.django_db


def print_short_cut(response):
    print(f'\n---- API Path: {response.request["PATH_INFO"]} '
          f'\n---- Response: {response.json()}')


class ImgUploadTestCase(TestCase):

    def setUp(self):
        user_token = mixer.blend(UserToken)
        self.headers = {
            'HTTP_X_TOKEN': user_token.token_string,
            'HTTP_X_CID': str(user_token.user.client.id),
        }
        file_path = request.urlretrieve('http://n.sinaimg.cn/sinacn/20170609/84da-fyfzsyc1766613.jpg')[0]
        self.img_file = SimpleUploadedFile(
            name='test_image.jpg',
            content=open(pathlib.Path(file_path), 'rb').read()
        )

    def test_api_img_upload(self):
        path = '/api/img/upload/'
        # print(type(self.img_file.file))
        response = self.client.post(path=path, data={'img': self.img_file}, format='multipart', **self.headers)
        print_short_cut(response)

    # def test_regular(self, empty=False):
    #     response = self.api_img_upload()
    #     print_short_cut(response)
    #     data = response.json().get('d')
    #     self.assertIsNot(bool(data), empty)

    # def test_without_img(self):
    #     self.headers = {}
    #     self.test_regular(empty=True)
    #
    # def test_with_wrong_headers(self):
    #     self.headers = {
    #         'HTTP_X_TOKEN': 'wrong_token',
    #         'HTTP_X_CID': '-1'
    #     }
    #     self.test_regular(empty=True)
    #
    # def test_without_headers(self):
    #     self.headers = {}
    #     self.test_regular(empty=True)

