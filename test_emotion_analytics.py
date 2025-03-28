import sounddevice as sd
import soundfile as sf
import time
import speech_recognition as sr
from pyAudioAnalysis import audioTrainTest as aT

# モデル名とモデルタイプ（モデルファイルが存在することを確認してください）
MODEL_NAME = "mySVMModel"
MODEL_TYPE = "svm"

def record_audio(filename, duration=3, sr=16000):
    """マイクから音声を録音し、WAVファイルとして保存する関数"""
    print("録音開始...")
    try:
        audio = sd.rec(int(duration * sr), samplerate=sr, channels=1)
        sd.wait()
        sf.write(filename, audio, sr)
        print("録音終了")
    except Exception as e:
        print("録音中にエラーが発生しました:", e)
        raise e

def get_voice_input(timeout=5):
    """
    マイクから音声入力を取得し、Googleの音声認識APIで日本語テキストに変換する関数
    ※インターネット接続が必要です。
    """
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("ご返答をどうぞ（「はい」または「いいえ」）：")
        try:
            audio = recognizer.listen(source, timeout=timeout)
            text = recognizer.recognize_google(audio, language="ja-JP")
            print("認識結果:", text)
            return text.lower()
        except sr.WaitTimeoutError:
            print("音声入力のタイムアウトが発生しました。")
            return ""
        except sr.UnknownValueError:
            print("音声を認識できませんでした。")
            return ""
        except Exception as e:
            print("音声認識中にエラーが発生しました:", e)
            return ""

while True:
    audio_file = "temp_recording.wav"
    # 1) 録音してファイル保存
    try:
        record_audio(audio_file, duration=3)
    except Exception:
        print("録音処理でエラーが発生したため、このループはスキップします。")
        continue

    # 2) 分類実行
    try:
        result, probability, class_names = aT.file_classification(audio_file, MODEL_NAME, MODEL_TYPE)
    except Exception as e:
        print("分類中にエラーが発生しました:", e)
        continue

    # モデルが見つからなかった場合や分類に失敗している場合のチェック
    if not isinstance(class_names, list):
        print("モデルが見つからないか、分類に失敗しました。")
        continue

    try:
        emotion_label = class_names[int(result)]
    except Exception as e:
        print("感情ラベルの取得に失敗しました:", e)
        continue

    print("推定された感情:", emotion_label)

    # 3) 感情に応じた応答
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
    else:
        print("未知の感情です。")

    # 4) 音声入力でループ
