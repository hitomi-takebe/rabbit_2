from pyAudioAnalysis import audioTrainTest as aT

data_dirs = [
    "./emotion_date/anger",
    "./emotion_date/disgust",
    "./emotion_date/fear",
    "./emotion_date/happy",
    "./emotion_date/sad",
    "./emotion_date/surprise",
]

# 正しく引数を設定したバージョン
aT.extract_features_and_train(
    data_dirs,
    1.0,
    1.0,
    0.05,
    0.025,
    "svm",
    "emotion_svm_model"
)
