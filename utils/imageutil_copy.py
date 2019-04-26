import json
import math
import pathlib

from PIL import Image
from django.conf import settings
from django.core.files import File
from djchoices import DjangoChoices, ChoiceItem
from rest_framework import status
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.iai.v20180301 import iai_client, models


class ImgSegments(DjangoChoices):
    AVATAR = ChoiceItem('avatar')
    FULL = ChoiceItem('full')
    FACE = ChoiceItem('face')
    EYEBROW = ChoiceItem('eyebrow')
    MOUTH = ChoiceItem('mouth')
    NOSE = ChoiceItem('nose')


def get_img_path(segment, person_result, save=False):
    """
    :param segment:         需要获取的人脸的部位
    :param person_result:   取出 client_id 和 face_img_name
    :param save:            True：获取保存的绝对路径  False：获取相对路径
    :return:                相对路径  facial/{client_id}/avatar/{img_md5}.jpg || png
    """
    if segment not in ImgSegments.values:
        raise ValueError('segment invalid')

    init_path = pathlib.Path(settings.PRO_DIR)
    element_path = init_path.joinpath(str(person_result.user.client_id))
    element_path = element_path.joinpath(segment)

    if save:
        prefix_dir = pathlib.Path(settings.UPLOAD_DIR)
        element_path = prefix_dir.joinpath(element_path)
        element_path.mkdir(parents=True, exist_ok=True)  # 创建路径如果不存在

    img_path = element_path.joinpath(person_result.face_img_name).as_posix()

    return img_path


class FaceCrop:
    def __init__(self, image: File, api_data: dict, person_result):
        """
        :param image:           将要被裁剪的人脸图片
        :param api_data:        通过腾讯云人脸识别api返回的人脸数据
        :param person_result:   定义将要被保存的结果的路径和名称
        """
        self.origin_img = image
        self.img = Image.open(image)
        self.person_result = person_result

        # 数据整理
        self.api_data = api_data
        self.face_data = api_data['FaceInfos'][0]
        self.features_data = api_data['FaceShapeSet'][0]

        # 旋转条件数据
        self.center_point = (self.img.width / 2, self.img.height / 2)
        self.angle = api_data['FaceInfos'][0]['FaceAttributesInfo']['Roll']
        self.rotated = False

    def crop_and_save(self):
        self._crop_and_save(feature_points=self.face_points, feature_type=ImgSegments.FACE)
        self.img = self._rotate_image(image=self.img)
        self._crop_and_save(feature_points=self.eyebrow_points, feature_type=ImgSegments.EYEBROW)
        self._crop_and_save(feature_points=self.nose_points, feature_type=ImgSegments.NOSE)
        self._crop_and_save(feature_points=self.mouth_points, feature_type=ImgSegments.MOUTH)
        return self._rotated_api_data

    @property
    def face_points(self):
        self.face_left = self.face_data['X']
        self.face_right = self.face_left + self.face_data['Width']
        top = self.face_data['Y']
        bottom = top + self.face_data['Height']

        if self.rotated:
            # 旋转脸的坐标。# 在原图旋转之后生效
            polygon = [(self.face_left, top), (self.face_right, top), (self.face_right, bottom),
                       (self.face_left, bottom)]
            face_polygon = self._rotate_polygon(polygon)
            face_range = self._range_point(points=face_polygon)

            self.face_left = face_range['min_x']
            top = face_range['min_y']
            self.face_right = face_range['max_x']
            bottom = face_range['max_y']

        return self.face_left, top, self.face_right, bottom

    @property
    def eyebrow_points(self):
        eyebrow_points = self.features_data['LeftEyeBrow']
        eyebrow_points += self.features_data['RightEyeBrow']
        eyebrow_range = self._range_point(eyebrow_points)
        return self._get_points(eyebrow_range)

    @property
    def nose_points(self):
        nose_range = self._range_point(self.features_data['Nose'])
        return self._get_points(nose_range)

    @property
    def mouth_points(self):
        mouth_range = self._range_point(self.features_data['Mouth'])
        return self._get_points(mouth_range)

    def _get_points(self, points_range):
        return self.face_left, points_range['min_y'], self.face_right, points_range['max_y']

    def _crop_and_save(self, feature_points, feature_type):
        feature_obj = self.img.crop(feature_points)
        if not self.rotated:
            feature_obj = self._rotate_image(feature_obj)  # 在原图旋转之前生效
        self._save_shortcut(feature_type=feature_type, file=feature_obj)

    def _save_shortcut(self, feature_type, file):
        save_path = get_img_path(segment=feature_type, save=True, person_result=self.person_result)
        if feature_type == ImgSegments.FULL:  # 原图保存
            with pathlib.Path(save_path).open('wb+') as des:
                for chunk in self.origin_img.chunks():
                    des.write(chunk)
        file.save(fp=save_path)

    def _range_point(self, points):
        points = [self._rotate_point(point=(point['X'], point['Y'])) for point in points]
        range_x = [x for x, y in points]
        range_y = [y for x, y in points]
        return {'max_x': max(range_x), 'min_x': min(range_x),
                'max_y': max(range_y), 'min_y': min(range_y)}

    def _rotate_image(self, image):
        if image == self.img:
            self.rotated = True
        return image.rotate(angle=-self.angle, resample=Image.BICUBIC)

    def _rotate_point(self, point: tuple) -> tuple:
        angle_rad = math.radians(self.angle % 360)

        new_point = (point[0] - self.center_point[0], point[1] - self.center_point[1])
        new_point = (new_point[0] * math.cos(angle_rad) - new_point[1] * math.sin(angle_rad),
                     new_point[0] * math.sin(angle_rad) + new_point[1] * math.cos(angle_rad))
        new_point = (new_point[0] + self.center_point[0], new_point[1] + self.center_point[1])
        return new_point

    def _rotate_polygon(self, polygon: list) -> list:
        rotated_polygon = [self._rotate_point(corner) for corner in polygon]
        return rotated_polygon

    @property
    def _rotated_api_data(self):
        """ 前端已自行计算 """
        return self.api_data


def face_api(base64_img: str, client):
    try:
        # 实例化一个认证对象，入参需要传入腾讯云账户secretId，secretKey
        cred = credential.Credential(secretId=client.qcloud_app_id, secretKey=client.qcloud_app_secret)

        # 实例化要请求产品(以iai为例)的client对象
        client = iai_client.IaiClient(credential=cred, region=client.qcloud_region)

        # 人脸检测请求对象
        detect_request = models.DetectFaceRequest()
        detect_request.Image = base64_img
        detect_request.NeedFaceAttributes = 1
        detect_request.NeedQualityDetection = 1

        # 五官分析请求对象
        analyze_requset = models.AnalyzeFaceRequest()
        analyze_requset.Image = base64_img

        # 通过client对象调用想要访问的接口，需要传入请求对象
        detect_response = client.DetectFace(detect_request)
        analyze_response = client.AnalyzeFace(analyze_requset)

        # 返回字典对象给Response
        api_result = json.loads(detect_response.to_json_string())

        # 加入五官分析结果
        api_result.update({
            'FaceShapeSet': json.loads(analyze_response.to_json_string()).get('FaceShapeSet')
        })
        status_code = status.HTTP_200_OK

    except TencentCloudSDKException as err:
        api_result = err.message
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return api_result, status_code


class TXFacialAPI:
    def __init__(self, base64_img: str, client, **options):
        """
        虽然不知道有没有必要 TODO 做成可以通过 **options，即一个字典，控制传到 腾讯api 的参数
        :param base64_img:
        :param client:
        :param options:
        """
        # 实例化一个认证对象，入参需要传入腾讯云账户secretId，secretKey
        cred = credential.Credential(secretId=client.qcloud_app_id, secretKey=client.qcloud_app_secret)
        # 实例化要请求产品(以iai为例)的client对象
        self.client = iai_client.IaiClient(credential=cred, region=client.qcloud_region)
        # TODO 加判断，是url还是base64
        self.image = base64_img

    def DetectFace(self):
        # 人脸检测请求对象
        detect_request = models.DetectFaceRequest()
        detect_request.Image = self.image
        detect_request.NeedFaceAttributes = 1
        detect_request.NeedQualityDetection = 1