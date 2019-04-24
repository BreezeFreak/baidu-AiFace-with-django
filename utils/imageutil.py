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
    :param segment:         which part of the face
    :param person_result:   to specify the file path (client_id) and file name (img_md5)
    :param save:            True：return a absolute path for saving file
                            False：return a relative path for combining url
    :return:                path pattern: facial/{client_id}/{segment}/{img_md5}.jpg || png
    """
    if segment not in ImgSegments.values:
        raise ValueError('segment invalid')

    init_path = pathlib.Path(settings.PRO_DIR)
    element_path = init_path.joinpath(str(person_result.user.client_id))
    element_path = element_path.joinpath(segment)

    if save:
        prefix_dir = pathlib.Path(settings.UPLOAD_DIR)
        element_path = prefix_dir.joinpath(element_path)
        element_path.mkdir(parents=True, exist_ok=True)  # mkdir if doesn't exist

    img_path = element_path.joinpath(person_result.face_img_name).as_posix()

    return img_path


def rotate_point(point: tuple, angle, origin=(0, 0)) -> tuple:
    """
    :param point: coordinate to be rotated
    :param angle: rotate angel
    :param origin: base center coordinate of rotation
    :return: (x, y)
    """
    angle_rad = math.radians(angle % 360)

    new_point = (point[0] - origin[0], point[1] - origin[1])
    new_point = (new_point[0] * math.cos(angle_rad) - new_point[1] * math.sin(angle_rad),
                 new_point[0] * math.sin(angle_rad) + new_point[1] * math.cos(angle_rad))

    new_point = (new_point[0] + origin[0], new_point[1] + origin[1])
    return new_point


def rotate_polygon(polygon: list, angle, origin=(0, 0)) -> list:
    """
    :param polygon: list of tuple
    :param angle:
    :param origin:
    :return: [(x, y), (x, y), ...]
    """
    rotated_polygon = []
    for corner in polygon:
        rotated_corner = rotate_point(corner, angle, origin)
        rotated_polygon.append(rotated_corner)
    return rotated_polygon


def face_api(base64_img: str):
    try:
        # init a credential object
        cred = credential.Credential(secretId=settings.QCLOUD_SID, secretKey=settings.QCLOUD_SKEY)

        # init a client object
        client = iai_client.IaiClient(credential=cred, region='ap-guangzhou')

        # request object
        detect_request = models.DetectFaceRequest()
        detect_request.Image = base64_img
        detect_request.NeedFaceAttributes = 1
        detect_request.NeedQualityDetection = 1

        analyze_requset = models.AnalyzeFaceRequest()
        analyze_requset.Image = base64_img

        # pass request object to response object
        detect_response = client.DetectFace(detect_request)
        analyze_response = client.AnalyzeFace(analyze_requset)

        # Response needs a json object
        api_result = json.loads(detect_response.to_json_string())

        # add analyze_data
        api_result.update({
            'FaceShapeSet': json.loads(analyze_response.to_json_string()).get('FaceShapeSet')
        })
        status_code = status.HTTP_200_OK

    except TencentCloudSDKException as err:
        api_result = err.message
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return api_result, status_code


def face_segments_save(data: dict, image: File, person_result):
    img = Image.open(image)

    # rotate center coordinate
    x0 = img.width / 2
    y0 = img.height / 2

    # rotate origin image
    angle = data['FaceInfos'][0]['FaceAttributesInfo']['Roll']

    img = img.rotate(angle=-angle, resample=Image.BICUBIC)

    def rotate_shortcut(segment_data):
        segment_data = [rotate_point(origin=(x0, y0), point=(point['X'], point['Y']), angle=angle) for point in
                        segment_data]
        return [y for x, y in segment_data]

    def save_shortcut(segment, file):
        save_path = get_img_path(segment=segment, save=True, person_result=person_result)
        file.save(fp=save_path)

    face_data = data['FaceInfos'][0]

    # face origin coordinate
    left = face_data['X']
    right = left + face_data['Width']
    top = face_data['Y']
    bottom = top + face_data['Height']

    face_center = (left + face_data['Width']/2, top + face_data['Height']/2)
    face_center = rotate_point(origin=(x0, y0), point=face_center, angle=angle)

    # here cause some problem, right or bottom larger than left or top
    left = face_center[0] - face_data['Width']/2
    right = face_center[1] + face_data['Width']/2
    top = face_center[0] - face_data['Height']/2
    bottom = face_center[1] + face_data['Height']/2

    # # face coordinate rotate # after img.rotate
    # polygon = [(left, top), (right, top), (right, bottom), (left, bottom)]
    # face_polygon = rotate_polygon(origin=(x0, y0), polygon=polygon, angle=angle)
    # horizontal = [x for x, y in face_polygon]
    # vertical = [y for x, y in face_polygon]
    #
    # left = min(horizontal)
    # top = min(vertical)
    # # right = left + face_data['Width']
    # # bottom = top + face_data['Height']
    # right = max(horizontal)
    # bottom = max(vertical)

    # face crop
    face = img.crop((left, top, right, bottom))
    # face = face.rotate(angle=-angle, resample=Image.BICUBIC)  # before img.rotate
    save_shortcut(segment=ImgSegments.FACE, file=face)

    segments_data = data['FaceShapeSet'][0]

    # eyebrow coordinate
    eyebrow_data = segments_data['LeftEyeBrow']
    eyebrow_data += segments_data['RightEyeBrow']
    eyebrow_height = rotate_shortcut(eyebrow_data)
    # eyebrow crop
    eyebrow = img.crop((left, min(eyebrow_height), right, max(eyebrow_height)))
    save_shortcut(segment=ImgSegments.EYEBROW, file=eyebrow)

    # nose coordinate
    nose_height = rotate_shortcut(segments_data['Nose'])
    # nose crop
    nose = img.crop((left, min(nose_height), right, max(nose_height)))
    save_shortcut(segment=ImgSegments.NOSE, file=nose)

    # mouth coordinate
    mouth_height = rotate_shortcut(segments_data['Mouth'])
    # mouth crop
    mouth = img.crop((left, min(mouth_height), right, max(mouth_height)))
    save_shortcut(segment=ImgSegments.MOUTH, file=mouth)

    # save the origin full image
    file_path = get_img_path(segment=ImgSegments.FULL, save=True, person_result=person_result)
    with pathlib.Path(file_path).open('wb+') as des:
        for chunk in image.chunks():
            des.write(chunk)

    # return data after rotated
    return data


def calculate_file(file_, hasher, chunk_size=65536):
    chunks = b''.join([chunk for chunk in file_.chunks(chunk_size)])
    result = {}

    result['base64'] = base64.b64encode(chunks).decode() if 'base64' in hasher else ''
    result['md5'] = hashlib.md5(chunks).hexdigest() if 'md5' in hasher else ''

    return result