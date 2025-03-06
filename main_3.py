import schedule
import time
import pyttsx3
from supabase import create_client, Client
import datetime
from langchain_openai import ChatOpenAI
import os
import speech_recognition as sr
import json
from langchain.prompts import PromptTemplate
import threading
import queue

# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase

# Supabaseクライアントの初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ChatOpenAIクライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

# グローバル変数の追加
mode_active = threading.Event()              # イベントフラグ
notification_queue = queue.Queue()           # 通知保留用のキュー

# ==========================================
# 音声出力管理：専用スレッドとキューを利用
# ==========================================
speech_queue = queue.Queue()

def speech_worker():
    """ キューからテキストを取り出して、音声合成を行う """
    engine = pyttsx3.init()
    while True:
        text = speech_queue.get()
        if text is None:  # 終了シグナル
            break
        engine.say(text)
        engine.runAndWait()
        speech_queue.task_done()

# 専用のスレッドで音声出力処理を開始
speech_thread = threading.Thread(target=speech_worker, daemon=True)
speech_thread.start()

def speak(text: str):
    """ 音声出力のリクエストをキューに追加 """
    speech_queue.put(text)

# ==========================================
# 音声認識
# ==========================================
def recognize_speech(timeout_seconds=120) -> str:
    """ マイクから音声を取得し、テキストに変換する """
    print(f"🎤 音声入力を待機... 最大{timeout_seconds}秒")
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
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

# ==========================================
# 意図判定（タスク登録 / SiriChat / Silent）
# ==========================================
def extract_intent_info(input_text: str) -> str:
    """ ユーザーの発話を3つのカテゴリに分類 """
    few_shot_prompt = """
あなたは音声アシスタントです。ユーザーの発話を以下の3つのカテゴリに分類してください。

1. TaskRegistration: ユーザーがタスクを登録したい（例：「タスクを登録」「タスク追加」など）
2. SiriChat: ユーザーが「Hi Siri」と話しかけた（例：「Hi Siri」「Hey Siri」など）
3. Silent: それ以外（無音、認識できなかった、その他）

出力は次の JSON 形式：
{{
  "intent": "<TaskRegistration | SiriChat | Silent>"
}}

=== FEW-SHOT EXAMPLES ===
User: "Hi Siri、タスクを登録する"
Assistant:
{{
  "intent": "TaskRegistration"
}}
User: "Hi Siri"
Assistant:
{{
  "intent": "SiriChat"
}}
User: "今日はいい天気ですね"
Assistant:
{{
  "intent": "Silent"
}}
=== END OF EXAMPLES ===

以下の発話：「{input_text}」
この発話の意図を判定し、**JSON形式** で答えてください。
"""
    prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
    final_prompt = prompt_template.format(input_text=input_text)
    response = chat_model.invoke(final_prompt)
    try:
        result = json.loads(response.content.strip())
        intent = result.get("intent", "Silent")
        return intent if intent in ["TaskRegistration", "SiriChat"] else "Silent"
    except (json.JSONDecodeError, AttributeError):
        print("⚠️ intent解析失敗:", response.content)
        return "Silent"

# ==========================================
# タスク通知
# ==========================================
def fetch_tasks():
    """ データベースから通知予定のタスクを取得 """
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").eq("user_id", CURRENT_USER_ID).execute()
    return response.data if response.data else []

def notify_and_wait_for_completion(task: dict):
    """ タスク通知を実行。C・Dモード中ならキューに保留 """
    if mode_active.is_set():
        print(f"🔄 通知保留: {task['title']}")
        notification_queue.put(task)
        return
    execute_task_notification(task)

def execute_task_notification(task: dict):
    """ 実際にタスク通知を行い、完了確認を行う """
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

def mark_task_completed(task_id: str):
    """ タスク完了をデータベースに登録 """
    now_str = datetime.datetime.now().isoformat()
    data = {"task_id": task_id, "user_id": CURRENT_USER_ID, "completed_at": now_str}
    supabase.table("task_completions").insert(data).execute()
    speak("タスクを完了登録しました。お疲れ様です。")

def process_pending_notifications():
    """ 保留された通知を処理する """
    while not notification_queue.empty():
        task = notification_queue.get()
        execute_task_notification(task)
        notification_queue.task_done()

# ==========================================
# ユーザー発話処理
# ==========================================
def process_user_input(user_text):
    """音声認識の結果を処理し、適切なモードを実行"""
    intent = extract_intent_info(user_text)
    print(f"🎙️ 推定Intent: {intent}")
    if intent == "TaskRegistration":
        mode_active.set()   # ← ここは必ず正しく閉じる
        insert_task()       # タスク登録モード
        mode_active.clear()
        process_pending_notifications()
    elif intent == "SiriChat":
        mode_active.set()
        siri_chat()         # Siri風雑談モード
        mode_active.clear()
        process_pending_notifications()
    else:
        print("⚠️ 無効な発話。何もしません。")


def siri_chat():
    """ Siri風雑談モード """
    speak("Siriモードです。何かお話ししますか？")

def insert_task():
    """ タスク登録モード（C）：タスクの詳細を取得して登録 """
    speak("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")
    time.sleep(0.5)  # 競合回避
    text_for_task = recognize_speech(timeout_seconds=120)
    if not text_for_task:
        speak("うまく聞き取れませんでした。タスク登録を中断します。")
        return
    # ※ここでは簡略化して、認識したテキストをそのままタスクタイトルとする
    title = text_for_task
    scheduled_time = "21:00:00"  # 固定の時刻（実際は抽出処理を実装）
    supabase.table("tasks").insert({"user_id": CURRENT_USER_ID, "title": title, "recurrence": "everyday", "scheduled_time": scheduled_time}).execute()
    speak("タスクを登録しました。")

# ==========================================
# バックグラウンド音声認識
# ==========================================
def background_listen():
    """ 音声認識をバックグラウンドで実行 """
    while True:
        user_text = recognize_speech(timeout_seconds=5)
        if user_text:
            process_user_input(user_text)

# ==========================================
# メインループ
# ==========================================
def main_loop():
    """ タスク通知を優先しつつ、音声認識をバックグラウンドで実行 """
    threading.Thread(target=background_listen, daemon=True).start()
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        for task in fetch_tasks():
            if task["scheduled_time"] == current_time:
                notify_and_wait_for_completion(task)
                break
        time.sleep(1)

if __name__ == "__main__":
    main_loop()

