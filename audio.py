# audio.py
import threading
import os
import tempfile
from gtts import gTTS
# import pyttsx3
import speech_recognition as sr
import time
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


# グローバルTTSエンジン（メインスレッドで利用）
# engine = pyttsx3.init()
speech_lock = threading.Lock()

# def speak(text: str):
#     """スレッドセーフにテキストを読み上げる（TTS）"""
#     with speech_lock:
#         engine.say(text)
#         engine.runAndWait()

def speak(text: str):
    with speech_lock:
        try:
            # gTTSで音声生成（日本語）
            tts = gTTS(text=text, lang="ja")
            # 一時的なMP3ファイルを作成
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_filename = fp.name
            tts.save(temp_filename)
            # mpg123で再生（-q は再生中のログを抑制）
            os.system("mpg123 -q " + temp_filename)
        finally:
            # 一時ファイルの削除
            if os.path.exists(temp_filename):
                os.remove(temp_filename)


def recognize_speech(timeout_seconds=5):
    recognizer = sr.Recognizer()

    # Python から利用できるマイクデバイスを取得
    mic_list = sr.Microphone.list_microphone_names()
    print("Available Microphones:", mic_list)

    # USBマイクまたはPulseAudioのデバイスを探す
    device_index = None
    for i, device in enumerate(mic_list):
        if "USB" in device or "pulse" in device.lower():
            device_index = i
            break

    if device_index is None:
        print("No suitable microphone found. Using default device.")
        device_index = 0  # デフォルトのマイクを使用

    print(f"Using Microphone device_index={device_index}")

    with sr.Microphone(device_index=device_index) as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source, timeout=timeout_seconds)

    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return "Could not understand audio"
    except sr.RequestError:
        return "Error with speech recognition API"

        
# audio.py
# import threading

# def recognize_speech(timeout_seconds=120) -> str:
#     """
#     マイクから音声を取得する代わりに、チャット入力（テキスト入力）を代用します。
#     ユーザーが timeout_seconds 内に入力しなかった場合はタイムアウトして、
#     「もう一度入力してください」と表示し、再度入力を促すループに入ります。
#     """
#     while True:
#         result = []

#         def input_thread():
#             # ユーザーにテキスト入力を促す
#             result.append(input("チャット入力してください: "))

#         t = threading.Thread(target=input_thread)
#         t.start()
#         t.join(timeout_seconds)  # 指定秒数だけ待つ

#         # タイムアウトしている場合は、まだ t が生きている
#         if t.is_alive():
#             print("タイムアウトしました。もう一度入力してください。")
#             # ※注意：input() はブロッキングのため、タイムアウト後もこのスレッドは残りますが、
#             # この例では簡易的に新しい入力スレッドを起動して再度入力を待ちます。
#             continue

#         # 入力が完了していれば、result に値が入っているはず
#         if result:
#             print("入力結果:", result[0])
#             return result[0]
#         else:
#             print("入力が空です。もう一度入力してください。")
#             # 入力が空の場合も再度ループして入力を促す
#             continue
