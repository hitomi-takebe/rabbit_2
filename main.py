# main.py
import threading
import time
import datetime
from audio import recognize_speech
from intent import extract_intent_info
from task_registration import insert_task
from notifications import run_task_notifications, fetch_tasks, notify_and_wait_for_completion
from siri_chat import siri_chat
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


def process_user_input(user_text):
    """
    音声認識結果から意図を判定し、タスク登録または雑談の各機能を呼び出す。
    """
    intent = extract_intent_info(user_text)
    print(f"推定Intent: {intent}")
    if intent == "TaskRegistration":
        insert_task()
    elif intent == "SiriChat":
        siri_chat()
    else:
        print("無効な発話。何もしません。")

def background_listen():
    """
    音声認識をバックグラウンドスレッドで常に実行し、
    ユーザーの発話があれば対応する機能を呼び出す。
    """
    while True:
        user_text = recognize_speech(timeout_seconds=5)
        if user_text:
            process_user_input(user_text)

def main_loop():
    """
    メインループ:
    ・バックグラウンドで音声認識（ユーザー入力）を実行
    ・定期的にタスク通知のチェックを行う
    """
    listen_thread = threading.Thread(target=background_listen, daemon=True)
    listen_thread.start()
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        tasks = fetch_tasks()
        for task in tasks:
            if task["scheduled_time"] == current_time:
                notify_and_wait_for_completion(task)
                break
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
