import sounddevice as sd
import soundfile as sf
from pyAudioAnalysis import audioTrainTest as aT
import time

MODEL_NAME = "mySVMModel"
MODEL_TYPE = "svm"

def record_audio(filename, duration=3, sr=16000):
    print("録音開始...")
    audio = sd.rec(int(duration * sr), samplerate=sr, channels=1)
    sd.wait()
    sf.write(filename, audio, sr)
    print("録音終了")

while True:
    # 1) 録音してファイル保存
    audio_file = "temp_recording.wav"
    record_audio(audio_file, duration=3)

    # 2) 分類実行
    result, probability, class_names = aT.file_classification(audio_file, MODEL_NAME, MODEL_TYPE)
    emotion_label = class_names[int(result)]
    print("推定された感情:", emotion_label)

    # 3) 応答やロジック
    if emotion_label == "anger":
        print("怒っているね、どうしたの？落ち着いて話してみよう。")
    elif emotion_label == "disgust":
        print("嫌がっているね。")
    elif emotion_label == "fear":
        print("恐れているね。勇気出して。")
    elif emotion_label == "happy":
        print("嬉しそうだね！話を続けて。")
    elif emotion_label == "sad":
        print("悲しそう....。話を続けて。")
    elif emotion_label == "surprise":
        print("驚いたね！話を続けて。")

    # 4) ループ終了判定
    print("もう一度試しますか？(y/n)")
    ans = input().lower()
    if ans != 'y':
        break
    time.sleep(1)