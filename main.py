# main.py
import time
import datetime
import threading
import queue
from audio import recognize_speech
from intent import extract_intent_info
from task_registration import insert_task
from notifications import fetch_tasks, notify_and_wait_for_completion
from siri_chat import siri_chat
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase

# タスク通知を一時保管するキュー
notification_queue = queue.Queue()

def process_user_input(user_text):
    """
    音声認識結果から意図を判定し、対応する機能を呼び出す関数。
    
    分岐:
      - TaskRegistration: タスク登録機能 (task_registration.py) を呼び出す
      - SiriChat: 雑談機能 (siri_chat.py) を呼び出す
      - Silent: 発言がなかった場合は何もしない
    """
    intent = extract_intent_info(user_text)
    print(f"推定Intent: {intent}")
    
    if intent == "TaskRegistration":
        insert_task()
    elif intent == "SiriChat":
        siri_chat()
    elif intent == "Silent":
        print("発言が認識されなかったため、何も処理しません。")
    else:
        print("不明な意図です。何も処理しません。")

def task_monitor():
    """
    別スレッドで実行するタスク監視ループ。
    現在時刻に合わせたタスクがあれば、通知用キューに追加する。
    「予定時刻 = 現在時刻」として、遅延しても通知が実施されるようにする。
    """
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        tasks = fetch_tasks()
        for task in tasks:
            # すでに通知済みの場合の管理は必要ですが、ここでは簡単化のため毎回キューに入れる例です。
            if task["scheduled_time"] == current_time:
                # 既にキューに入っているか確認（重複防止のため）――必要ならチェックを追加する
                notification_queue.put(task)
        time.sleep(1)  # 1秒ごとにチェック

def process_notification_queue():
    """
    メインループの中で、音声入力処理が終わった後に、キューに溜まったタスク通知を処理する関数。
    """
    while not notification_queue.empty():
        task = notification_queue.get()
        notify_and_wait_for_completion(task)
        notification_queue.task_done()

def main_loop():
    """
    メインループ:
      ① 音声入力を短いタイムアウト（3秒）でチェックし、あれば優先的に処理する。
      ② 音声入力処理が終わったら、キューに保管されているタスク通知を処理する。
    """
    while True:
        # ① 音声入力のチェック
        user_text = recognize_speech(timeout_seconds=3)
        if user_text:
            process_user_input(user_text)
        
        # ② 音声入力処理が終わったら、キューにあるタスク通知を実行
        process_notification_queue()
        
        time.sleep(0.5)

if __name__ == "__main__":
    # タスク監視スレッドを開始（このスレッドは常にバックグラウンドでタスクの監視・キューへの追加を行う）
    monitor_thread = threading.Thread(target=task_monitor, daemon=True)
    monitor_thread.start()
    
    # メインループ開始（音声入力処理と通知キューの処理を行う）
    main_loop()
