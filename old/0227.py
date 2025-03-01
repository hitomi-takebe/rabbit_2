import datetime
import json
import random
import time

import speech_recognition as sr
import pyttsx3
from supabase import create_client, Client

# --- Supabaseの設定 ---
SUPABASE_URL = ""
SUPABASE_KEY = ""
CURRENT_USER_ID = ""  # 対象ユーザーのUUID

# Supabaseクライアントの初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- 音声認識と音声合成の設定 ---
def speak(text: str):
    """指定したテキストを音声で出力する"""
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for voice in voices:
        if "ja_" in voice.id or "Japanese" in voice.name:
            engine.setProperty('voice', voice.id)
            break
    engine.setProperty('rate', 150)
    engine.say(text)
    engine.runAndWait()


def listen_for_task() -> str:
    """マイクから音声を取得し、テキストに変換して返す"""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("話してください...")
        speak("タスクを追加するために、話してください。")
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        print("認識結果:", text)
        return text
    except sr.UnknownValueError:
        print("音声を認識できませんでした。")
        speak("音声を認識できませんでした。")
    except sr.RequestError as e:
        print("音声認識サービスに接続できませんでした。", e)
        speak("音声認識サービスに接続できませんでした。")
    return None


# --- Supabase DB操作 ---
def insert_task(title: str):
    """Supabaseのtasksテーブルにタスクを登録する"""
    now = datetime.datetime.now().isoformat()
    task_data = {
        "user_id": CURRENT_USER_ID,
        "title": title,
        "description": "音声入力で登録されたタスク",
        "scheduled_time": now,
        "recurrence": "none",
        "next_occurrence": now
    }
    try:
        response = supabase.table("tasks").insert(task_data).execute()
        
        if response.data:
            print("タスクを追加しました:", response.data)
        else:
            print("データの挿入に失敗しました:", response)

    except Exception as e:
        print("エラーが発生しました:", str(e))



def get_tasks():
    try:
        response = supabase.table("tasks").select("*").execute()
        
        if response.data:  # データが取得できた場合
            print("取得したタスク:", response.data)
            return response.data
        else:  # データがない or 取得失敗
            print("タスクの取得に失敗しました:", response)
            return []

    except Exception as e:
        print("エラーが発生しました:", str(e))
        return []


def remind_task():
    """登録されたタスクの中からランダムに選んでリマインドする"""
    tasks = get_tasks()
    if not tasks:
        speak("タスクが登録されていません。")
        return
    task = random.choice(tasks)
    message = f"リマインドです。{task['title']}を実施しましたか？"
    print(message)
    speak(message)


# --- メイン処理 ---
def main():
    task_title = listen_for_task()
    if task_title:
        insert_task(task_title)
    else:
        print("タスクが認識されなかったため、登録をスキップします。")

    tasks = get_tasks()
    if tasks:
        print("現在のタスク一覧:")
        for task in tasks:
            print(" -", task["title"])
    else:
        print("タスクは存在しません。")

    speak("10秒後にリマインドを実行します。")
    time.sleep(10)
    remind_task()


if __name__ == "__main__":
    main()
