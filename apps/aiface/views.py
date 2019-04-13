import base64

from PIL import Image
from aip import AipFace
from django.conf import settings

from django.http import JsonResponse
from hurry.filesize import size




def index(request):
    img = request.FILES.get('img')
    valid = img_validate(img)
    if valid != 1:
        return JsonResponse({'msg': valid})

    result = aiface_baidu_api(img)
    return JsonResponse(result)


def img_validate(img):  # 可以丢在serializer
    acceptable_content_type = ['image/jpeg', 'image/png']

    if not img:
        return '没有图片'

    if img.size > (10 * 1024 * 1024):
        return f'图片大小: {size(img.size)}, 超过10M'

    if img.content_type not in acceptable_content_type:
        return f'图片格式错误{img.content_type}'

    return 1


def aiface_baidu_api(img):
    client = AipFace(settings.APP_ID, settings.API_KEY, settings.SECRET)

    with img.open('rb') as image_file:
        encoded_string = base64.b64encode(image_file.read())

    image = encoded_string.decode()
    image_type = "BASE64"
    face_field = 'age,beauty,expression,face_shape,gender,glasses,landmark,landmark72,race,quality,eye_status,face_type'
    options = {
        'face_field': face_field,
        'max_face_num': 2,
        'face_type': 'LIVE',
    }
    result = client.detect(image, image_type, options)
    return result

# def cut_test(img):  # next step
#     from django.core.files.uploadedfile import InMemoryUploadedFile
#     Image.crop

