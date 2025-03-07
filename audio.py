# audio.py
import threading
import pyttsx3
import speech_recognition as sr
import time
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase

# グローバルTTSエンジン（メインスレッドで利用）
engine = pyttsx3.init()
speech_lock = threading.Lock()

def speak(text: str):
    """スレッドセーフにテキストを読み上げる（TTS）"""
    with speech_lock:
        engine.say(text)
        engine.runAndWait()

# def recognize_speech(timeout_seconds=120) -> str:
#     """
#     マイクから音声を取得し、日本語で認識して文字列を返す。
#     timeout_seconds: 録音の上限秒数
#     """
#     print(f"音声入力を待機しています... 最大{timeout_seconds}秒")
#     recognizer = sr.Recognizer()
#     with sr.Microphone() as source:
#         recognizer.adjust_for_ambient_noise(source)
#         try:
#             audio = recognizer.listen(source, timeout=timeout_seconds, phrase_time_limit=timeout_seconds)
#         except sr.WaitTimeoutError:
#             print("指定時間内に音声が入力されませんでした。")
#             return ""
#     try:
#         text = recognizer.recognize_google(audio, language="ja-JP")
#         print("認識結果:", text)
#         return text
#     except sr.UnknownValueError:
#         print("音声を認識できませんでした。")
#         return ""
#     except sr.RequestError:
#         print("音声認識サービスに接続できませんでした。")
#         return ""


        
# audio.py
import threading

def recognize_speech(timeout_seconds=120) -> str:
    """
    マイクから音声を取得する代わりに、チャット入力（テキスト入力）を代用します。
    ユーザーが timeout_seconds 内に入力しなかった場合はタイムアウトして、
    「もう一度入力してください」と表示し、再度入力を促すループに入ります。
    """
    while True:
        result = []

        def input_thread():
            # ユーザーにテキスト入力を促す
            result.append(input("チャット入力してください: "))

        t = threading.Thread(target=input_thread)
        t.start()
        t.join(timeout_seconds)  # 指定秒数だけ待つ

        # タイムアウトしている場合は、まだ t が生きている
        if t.is_alive():
            print("タイムアウトしました。もう一度入力してください。")
            # ※注意：input() はブロッキングのため、タイムアウト後もこのスレッドは残りますが、
            # この例では簡易的に新しい入力スレッドを起動して再度入力を待ちます。
            continue

        # 入力が完了していれば、result に値が入っているはず
        if result:
            print("入力結果:", result[0])
            return result[0]
        else:
            print("入力が空です。もう一度入力してください。")
            # 入力が空の場合も再度ループして入力を促す
            continue
