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

# 🔥 グローバル変数
engine = pyttsx3.init()
speech_lock = threading.Lock()  # 🔥 音声合成の競合を防ぐ
notification_queue = queue.Queue()  # 🔥 通知の保留用キュー
mode_active = threading.Event()  # 🔥 C・Dモード実行中フラグ

def speak(text: str):
    """指定したテキストを音声で読み上げる（スレッドセーフ）"""
    with speech_lock:  # 🔥 他のスレッドと競合しないようにロック
        engine.say(text)
        engine.runAndWait()

# =========================
# 🔊 音声合成 (TTS)
# =========================
def recognize_speech(timeout_seconds=120) -> str:
    """音声入力を取得し、日本語で認識してテキスト化"""
    print(f"音声入力を待機... 最大{timeout_seconds}秒")
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=timeout_seconds, phrase_time_limit=timeout_seconds)
        except sr.WaitTimeoutError:
            print("指定時間内に音声が入力されませんでした。")
            return ""
    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        print("認識結果:", text)
        return text
    except sr.UnknownValueError:
        print("音声を認識できませんでした。")
        return ""
    except sr.RequestError:
        print("音声認識サービスに接続できませんでした。")
        return ""

# =========================
# 🎯 意図の判定
# =========================

def extract_intent_info(input_text: str) -> str:
    """ユーザーの発話意図を3つのカテゴリに分類（タスク登録 / SiriChat / 無音）"""
    few_shot_prompt = """
あなたは音声アシスタントです。ユーザーの発話を以下の3つのカテゴリのいずれかに分類してください。

1. **TaskRegistration**: ユーザーがタスクを登録したい（例：「タスクを登録」「タスク追加」など）
2. **SiriChat**: ユーザーが「Hi Siri」と話しかけた（例：「Hi Siri」「Hey Siri」など）
3. **Silent**: ユーザーが無言だった、または認識できなかった

出力は次の JSON 形式：
{{
  "intent": "<TaskRegistration | SiriChat | Silent>"
}}

=== FEW-SHOT EXAMPLES ===

User: "タスクを登録したい"
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

User: "お腹すいた"
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
        intent = result.get("intent", "Silent")# デフォルトは "Silent"
        return intent if intent in ["TaskRegistration", "SiriChat"] else "Silent"
    except (json.JSONDecodeError, AttributeError):
        print("intent解析失敗:", response.content)
        return "Silent"

# =========================
# 📅 タスク通知
# =========================
def fetch_tasks():
    """データベースから通知予定のタスクを取得"""
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").eq("user_id", CURRENT_USER_ID).execute()
    return response.data if response.data else []

def notify_and_wait_for_completion(task: dict):
    """タスク通知し、完了を待機（C・D 実行中なら後回し）"""
    if mode_active.is_set():
        notification_queue.put(task)  # 🔥 キューに追加
        return
    execute_task_notification(task)

# def schedule_notifications():
#     """タスク情報に基づき、毎日指定時間にリマインド通知をスケジュール"""
#     tasks = fetch_tasks()
#     for task in tasks:
#         title = task["title"]
#         scheduled_time = task["scheduled_time"]
#         if scheduled_time:
#             hour, minute, _ = map(int, scheduled_time.split(":"))
#             schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(notify_and_wait_for_completion, task)
#             print(f"📅 {hour:02d}:{minute:02d} に『{title}』を通知")

def execute_task_notification(task: dict):
    """タスク通知し、完了を待機"""
    title = task["title"]
    task_id = task["id"]
    speak(f"タスクの時間です。{title} をお願いします。")
    print(f"📢 通知: {title}")

    speak("完了したら『完了したよ』などと言ってください。")
    for _ in range(3):
        user_input = recognize_speech(timeout_seconds=60)
        if any(word in user_input for word in ["完了", "やった", "できた", "done"]):
            mark_task_completed(task_id)
            return
        else:
            speak("もう一度お願いします。")
    print("完了ワードなし。完了が確認できませんでした。また後でチェックします。")
    speak("完了が確認できませんでした。また後でチェックします。")

def mark_task_completed(task_id: str):
    """タスクを完了としてDBに登録"""
    now_str = datetime.datetime.now().isoformat()
    data = {"task_id": task_id, "user_id": CURRENT_USER_ID, "completed_at": now_str}
    response = supabase.table("task_completions").insert(data).execute()
    if response.data:
        print(f"✅ タスク完了: {response.data}")
        speak("タスクを完了登録しました。お疲れ様です。")
    else:
        print("❌ タスク完了登録失敗:", response)
        speak("タスク完了の登録に失敗しました。")

def process_pending_notifications():
    """ 🔥 保留された通知を処理 """
    while not notification_queue.empty():
        task = notification_queue.get()
        execute_task_notification(task)
        notification_queue.task_done()


# =========================
# 🎤 ユーザーの発話処理
# =========================
def process_user_input(user_text):
    """音声認識の結果を処理し、適切なモードを実行"""
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

def siri_chat():
    """Siri風雑談モード"""
    speak("Siriモードです。何かお話ししますか？")


# =========================
# 6. タスク登録 (DB挿入) + 音声応答
# =========================
def extract_task_info(input_text: str) -> dict:
    """
    ユーザーの発話からタスクのタイトルと予定時刻を抽出する
    出力形式:
    {
      "title": "タスク名",
      "scheduled_time": "HH:MM:SS"  # または null
    }
    """
    prompt = PromptTemplate(
        input_variables=["input_text"],
        template="""
        あなたはタスクの記述文から、タスクのタイトルと予定時刻（24時間表記のHH:MM:SS）を抽出するアシスタントです。
        以下の文章: 「{input_text}」
        から、
        {{
        "title": "<タスク名>",
        "scheduled_time": "<HH:MM:SS または null>"
        }}
        の形式のJSONのみを出力してください。
        """
    )
    final_prompt = prompt.format(input_text=input_text)
    response = chat_model.invoke(final_prompt)

    try:
        task_info = json.loads(response.content.strip("`"))
        return task_info
    except (json.JSONDecodeError, AttributeError) as e:
        print("タスク情報のJSON解析に失敗:", e)
        print("レスポンス:", response.content)
        return {}


def insert_task():
    """
    タスクの詳細を音声で取得 → OpenAIで解析 → SupabaseのDBにINSERT
    # """
    speak("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")  # プロンプトを音声で伝える
    text_for_task = recognize_speech(timeout_seconds=120)  # ここでは数値のみを渡す

    threading.Thread(target=speak, args=("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）",)).start()
    time.sleep(0.5)  # 🔥 競合回避
    text_for_task = recognize_speech(timeout_seconds=120)

    if not text_for_task:
        speak("うまく聞き取れませんでした。タスク登録を中断します。")
        return

    # タスク情報抽出
    task_info = extract_task_info(text_for_task)
    if not task_info or not task_info.get("title"):
        speak("タスクのタイトルが取得できませんでした。登録を中止します。")
        print("抽出結果:", task_info)
        return

    title = task_info["title"]
    scheduled_time = task_info.get("scheduled_time", None)

    # DBへINSERT
    data = {
        "user_id": CURRENT_USER_ID,
        "title": title,
        "recurrence": "everyday",  # 毎日タスクという例
        "scheduled_time": scheduled_time
    }
    try:
        res = supabase.table("tasks").insert(data).execute()
        if res.data:
            print("タスクを登録しました:", res.data)
            speak("タスクを登録しました。ありがとうございます。")
        else:
            print("タスク登録に失敗:", res)
            speak("タスク登録に失敗しました。")
    except Exception as e:
        print("DB処理でエラー:", e)
        speak("タスク登録の途中でエラーが発生しました。")

# =========================
# 🎯 メイン処理
# =========================

def background_listen():
    """音声認識をバックグラウンドで実行"""
    while True:
        user_text = recognize_speech(timeout_seconds=5)
        if user_text:
            process_user_input(user_text)

def main_loop():
    """通知を最優先しながら、音声認識を非同期で実行"""
    threading.Thread(target=background_listen, daemon=True).start()
    while True:
        for task in fetch_tasks():
            if task["scheduled_time"] == datetime.datetime.now().strftime("%H:%M:%S"):
                notify_and_wait_for_completion(task)
                break
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
