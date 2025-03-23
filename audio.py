# audio.py
import threading
import os
import sounddevice as sd
import tempfile
from gtts import gTTS
# import pyttsx3
import speech_recognition as sr
import time


speech_lock = threading.Lock()
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


#amivoiceを利用したもの
def recognize_speech(timeout_seconds=120) -> str:
    """
    マイクから音声を取得し、日本語で認識して文字列を返す。
    timeout_seconds: 録音の上限秒数
    """
    print(f"音声入力を待機しています... 最大{timeout_seconds}秒")
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=timeout_seconds, phrase_time_limit=timeout_seconds)
        except sr.WaitTimeoutError:
            print("指定時間内に音声が入力されませんでした。")
            return ""
        
    # speech_recognitionのAudioDataオブジェクトからWAVデータを取得し、一時的なWAVファイルに保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
        temp_wav = fp.name
        fp.write(audio.get_wav_data())

    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        # import amivoice  # amivoiceライブラリのインポート
        # client = amivoice.AmiVoiceClient(api_key="YOUR_API_KEY")
        # 同期的に音声認識を実施（認識結果が返るまでブロックします）
        # text = client.recognize(temp_wav)
        print("認識結果:", text)

          # 感情分析の結果処理と Supabase 登録を実施
        process_sentiment_and_save(temp_wav, text)

        return text
    except sr.UnknownValueError:
        print("音声を認識できませんでした。")
        return ""
    except sr.RequestError:
        print("音声認識サービスに接続できませんでした。")
        return ""
    finally:
        # 作成した一時ファイルを削除
        if os.path.exists(temp_wav):
            os.remove(temp_wav)



# analyze_sentiment 関数を先に定義する
def analyze_sentiment(file_path: str) -> dict:
    """
    ダミーの感情分析結果を返す関数です。
    実際には、ここで音声ファイル (file_path) を分析するAPI等にリクエストし、結果を取得してください。
    以下はサンプルとして2件のセグメントを返す例です。
    """
    return {
        "segments": [
            {
                "starttime": 1000,
                "endtime": 2000,
                "energy": 3,
                "content": 0,
                "upset": 0,
                "aggression": 0,
                "stress": 10,
                "uncertainty": 15,
                "excitement": 12,
                "concentration": 8,
                "emo_cog": 20,
                "hesitation": 5,
                "brain_power": 25,
                "embarrassment": 0,
                "intensive_thinking": 30,
                "imagination_activity": 7,
                "extreme_emotion": 0,
                "passionate": 0,
                "atmosphere": 0,
                "anticipation": 10,
                "dissatisfaction": 0,
                "confidence": 14
            },
            {
                "starttime": 2100,
                "endtime": 3000,
                "energy": 2,
                "content": 0,
                "upset": 0,
                "aggression": 0,
                "stress": 20,
                "uncertainty": 15,
                "excitement": 14,
                "concentration": 10,
                "emo_cog": 22,
                "hesitation": 6,
                "brain_power": 27,
                "embarrassment": 0,
                "intensive_thinking": 32,
                "imagination_activity": 5,
                "extreme_emotion": 1,
                "passionate": 0,
                "atmosphere": -1,
                "anticipation": 8,
                "dissatisfaction": 0,
                "confidence": 16
            }
        ]
    }

#音声認識を保存する

def process_sentiment_and_save(file_path: str, recognized_text: str) -> None:
    """
    指定された音声ファイル（file_path）に対して感情分析を実施し、
    セグメントごとに各指標の平均値を計算した上で、認識結果の全文（recognized_text）とともに
    Supabase の sentiment_averages テーブルに保存します。
    """
    # ダミーの感情分析結果を取得
    sentiment_result = analyze_sentiment(file_path)
    segments = sentiment_result.get("segments", [])
    
    if not segments:
        print("感情分析のセグメントが見つかりませんでした。")
        return

    sums = {}
    counts = {}
    for seg in segments:
        for key, value in seg.items():
            if key in ("starttime", "endtime"):
                continue
            if isinstance(value, (int, float)):
                sums[key] = sums.get(key, 0) + value
                counts[key] = counts.get(key, 0) + 1

    averages = { key: sums[key] / counts[key] for key in sums }
    print("感情分析の平均値:", averages)

    # Supabase に挿入するデータを作成（talk カラムに認識結果全文を保存）
    data = {
        "user_id": CURRENT_USER_ID,
        "talk": recognized_text,
        "energy": averages.get("energy"),
        "content": averages.get("content"),
        "upset": averages.get("upset"),
        "aggression": averages.get("aggression"),
        "stress": averages.get("stress"),
        "uncertainty": averages.get("uncertainty"),
        "excitement": averages.get("excitement"),
        "concentration": averages.get("concentration"),
        "emo_cog": averages.get("emo_cog"),
        "hesitation": averages.get("hesitation"),
        "brain_power": averages.get("brain_power"),
        "embarrassment": averages.get("embarrassment"),
        "intensive_thinking": averages.get("intensive_thinking"),
        "imagination_activity": averages.get("imagination_activity"),
        "extreme_emotion": averages.get("extreme_emotion"),
        "passionate": averages.get("passionate"),
        "atmosphere": averages.get("atmosphere"),
        "anticipation": averages.get("anticipation"),
        "dissatisfaction": averages.get("dissatisfaction"),
        "confidence": averages.get("confidence")
    }
    
    response = supabase.table("sentiment_averages").insert(data).execute()
    print("Supabaseへの登録結果:", response)
# #google speech to textを利用したもの
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