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

    with sr.Microphone(device_index=2) as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source, timeout=timeout_seconds)

    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return "Could not understand audio"
    except sr.RequestError:
        return "Error with speech recognition API"


mport threading
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


# def recognize_speech(timeout_seconds=5):
#     recognizer = sr.Recognizer()

#     with sr.Microphone(device_index=2) as source:
#         print("Listening...")
#         recognizer.adjust_for_ambient_noise(source)
#         audio = recognizer.listen(source, timeout=timeout_seconds)

#     try:
#         return recognizer.recognize_google(audio)
#     except sr.UnknownValueError:
#         return "Could not understand audio"
#     except sr.RequestError:
#         return "Error with speech recognition API"
        
# import speech_recognition as sr

def recognize_speech(timeout_seconds=5):
    recognizer = sr.Recognizer()

    # 利用可能なマイクをリストアップ
    mic_list = sr.Microphone.list_microphone_names()
    print("Available Microphones:", mic_list)

    # "USB" や "pulse" を含むデバイスを探す
    device_index = 2
    for i, device in enumerate(mic_list):
        if "USB" in device or "pulse" in device.lower():
            device_index = i
            break

    if device_index is None:
        print("No suitable microphone found. Using default device.")
        device_index = 0  # デフォルトのマイクを使用

    print(f"Using Microphone device_index={device_index}")

    try:
        with sr.Microphone(device_index=device_index) as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source, timeout=timeout_seconds)
        return recognizer.recognize_google(audio)

    except sr.RequestError:
        return "Error with speech recognition API"
    
    except sr.UnknownValueError:
        return "Could not understand audio"
    
    except Exception as e:
        print(f"Error: {e}")
        return None
