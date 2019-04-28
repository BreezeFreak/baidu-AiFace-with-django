from imageai.Prediction import ImagePrediction

import os

""" https://blog.51cto.com/13460911/2107499 """


def ImageAI(image_path):
    execution_path = os.getcwd()

    prediction = ImagePrediction()

    prediction.setModelTypeAsResNet()

    prediction.setModelPath(execution_path + "lib/learning_model/resnet50_weights_tf_dim_ordering_tf_kernels.h5")

    prediction.loadModel()

    predictions, percentage_probabilities = prediction.predictImage(image_path, result_count=5)

    for index in range(len(predictions)):
        print(predictions[index] + " : " + percentage_probabilities[index])

    return predictions
