import time
import pyttsx3
import datetime
import os
import speech_recognition as sr
import json
import threading
import queue

# ※ 必要に応じて、実際の設定値やライブラリのimport（例: supabase, ChatOpenAI等）を有効化してください
# from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase
# from supabase import create_client, Client
# from langchain_openai import ChatOpenAI
# from langchain.prompts import PromptTemplate

# ==================================================
# グローバル変数（モード管理、通知キュー、音声合成キュー）
# ==================================================
mode_active = threading.Event()         # タスク登録やSiriチャットなど、モードがアクティブかどうかを管理
notification_queue = queue.Queue()        # モード中に通知を保留するためのキュー
speech_queue = queue.Queue()              # 音声合成用のメッセージをためるキュー

# ==================================================
# 音声出力（メインスレッドで実行）
# ==================================================
def speak(text: str):
    """音声出力のリクエストをキューに追加する"""
    speech_queue.put(text)

def process_speech_queue():
    """
    メインスレッドで呼び出し、speech_queue から取り出したテキストを
    pyttsx3 で音声合成する（macの場合はdriverName='nsss'も検討可）
    """
    while not speech_queue.empty():
        text = speech_queue.get()
        try:
            engine = pyttsx3.init()  # macの場合、必要なら driverName='nsss' としてもよい
            engine.say(text)
            engine.runAndWait()      # run loop は必ずメインスレッドで実行
        finally:
            speech_queue.task_done()

# ==================================================
# 音声認識（パラメータ調整済み）
# ==================================================
def recognize_speech(timeout_seconds=120) -> str:
    """
    マイクから音声を取得し、GoogleのAPIを使ってテキストに変換する。
    ・dynamic_energy_threshold をオフにして、固定の energy_threshold を設定
    ・pause_threshold を 2.0秒に設定（ユーザーの一時停止をより寛容に扱う）
    """
    print(f"🎤 音声入力を待機... 最大{timeout_seconds}秒")
    recognizer = sr.Recognizer()
    
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = 4000  # 環境に合わせて適宜調整してください
    recognizer.pause_threshold = 2.0      # ユーザーが一時停止しても発話中と判断する時間を延長

    with sr.Microphone() as source:
        try:
            audio = recognizer.listen(source, timeout=timeout_seconds, phrase_time_limit=timeout_seconds)
        except sr.WaitTimeoutError:
            print("⚠️ 指定時間内に音声が入力されませんでした。")
            return ""
    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        print("✅ 認識結果:", text)
        return text
    except sr.UnknownValueError:
        print("⚠️ 音声を認識できませんでした。")
        return ""
    except sr.RequestError:
        print("⚠️ 音声認識サービスに接続できませんでした。")
        return ""

# ==================================================
# ユーザー発話の意図判定（簡易ロジック）
# ==================================================
def extract_intent_info(input_text: str) -> str:
    """
    ユーザーの発話から意図を抽出する。
    ・「タスク」が含まれる場合：TaskRegistration
    ・「Hi Siri」または「Hey Siri」が含まれる場合：SiriChat
    ・それ以外は Silent とする
    """
    if not input_text:
        return "Silent"
    if "タスク" in input_text:
        return "TaskRegistration"
    if "Hi Siri" in input_text or "Hey Siri" in input_text:
        return "SiriChat"
    return "Silent"

# ==================================================
# タスク通知・完了確認処理
# ==================================================
def fetch_tasks():
    """
    データベースから通知予定のタスクを取得（ダミー実装）
    ※実際は、supabase等を使って取得してください
    """
    return [
        {"id": 1, "title": "19時に晩ごはんを作る", "scheduled_time": "14:00:00", "recurrence": "everyday"},
        {"id": 2, "title": "21時にストレッチする", "scheduled_time": "21:00:00", "recurrence": "everyday"},
    ]

def notify_and_wait_for_completion(task: dict):
    """
    タスク通知を行う。
    ・モード中の場合は通知を保留し、後で処理する
    """
    if mode_active.is_set():
        print(f"🔄 通知保留: {task['title']}")
        notification_queue.put(task)
        return
    execute_task_notification(task)

def execute_task_notification(task: dict):
    """
    実際にタスクの通知を行い、ユーザーから完了報告を受け付ける。
    ・1回あたり最大60秒、計3回試みる構造です。
    """
    speak(f"タスクの時間です。{task['title']} をお願いします。")
    print(f"📢 通知: {task['title']}")
    speak("完了したら『完了したよ』などと言ってください。")
    
    for _ in range(3):
        user_input = recognize_speech(timeout_seconds=60)
        if any(word in user_input for word in ["完了", "やった", "できた", "done"]):
            mark_task_completed(task["id"])
            return
        else:
            speak("もう一度お願いします。")
    
    print("⚠️ 完了ワードが確認できませんでした。")
    speak("完了が確認できませんでした。また後でチェックします。")

def mark_task_completed(task_id):
    """
    タスク完了を登録（ダミー実装）。
    ※実際は、データベースへの登録処理等を実装してください
    """
    now_str = datetime.datetime.now().isoformat()
    print(f"完了登録: タスクID={task_id}, 完了時刻={now_str}")
    speak("タスクを完了登録しました。お疲れ様です。")

def process_pending_notifications():
    """保留された通知を処理する"""
    while not notification_queue.empty():
        task = notification_queue.get()
        execute_task_notification(task)
        notification_queue.task_done()

# ==================================================
# ユーザー発話処理
# ==================================================
def process_user_input(user_text):
    """音声認識の結果を処理し、適切なモードを実行する"""
    intent = extract_intent_info(user_text)
    print(f"🎙️ 推定Intent: {intent}")
    if intent == "TaskRegistration":
        mode_active.set()
        insert_task()
        mode_active.clear()
        process_pending_notifications()
    elif intent == "SiriChat":
        mode_active.set()
        siri_chat()
        mode_active.clear()
        process_pending_notifications()
    else:
        print("⚠️ 無効な発話。何もしません。")

def siri_chat():
    """Siri風雑談モード"""
    speak("Siriモードです。何かお話ししますか？")
    user_input = recognize_speech(timeout_seconds=15)
    if user_input:
        speak("なるほど、勉強になります！")

def insert_task():
    """タスク登録モード：ユーザーの発話をそのままタスク内容として登録する"""
    speak("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")
    time.sleep(0.5)
    text_for_task = recognize_speech(timeout_seconds=120)
    if not text_for_task:
        speak("うまく聞き取れませんでした。タスク登録を中断します。")
        return
    title = text_for_task
    scheduled_time = "21:00:00"  # ダミーの固定時間（実際は抽出処理等が必要）
    print(f"【DB登録】タスク: {title}, 時間: {scheduled_time}")
    speak("タスクを登録しました。")

# ==================================================
# バックグラウンド音声認識（サブスレッドで常時実行）
# ==================================================
def background_listen():
    while True:
        user_text = recognize_speech(timeout_seconds=5)
        if user_text:
            process_user_input(user_text)

# ==================================================
# メインループ（タスク通知と音声合成はメインスレッドで実行）
# ==================================================
def main_loop():
    # バックグラウンドで音声認識を常時実行
    threading.Thread(target=background_listen, daemon=True).start()

    while True:
        # 1) 現在時刻に合わせたタスクをチェックし通知
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        for task in fetch_tasks():
            if task["scheduled_time"] == current_time:
                notify_and_wait_for_completion(task)
                break

        # 2) メインスレッドで音声合成キューを処理
        process_speech_queue()

        time.sleep(1)

if __name__ == "__main__":
    main_loop()
