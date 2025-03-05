import schedule
import time
import pyttsx3
from supabase import create_client, Client
import datetime
from langchain_openai import ChatOpenAI
import os
import speech_recognition as sr
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID
from supabase import create_client, Client

#supabaseできたかなmouissyo
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ChatOpenAI（LangChain）クライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

# 音声エンジンの初期化
engine = pyttsx3.init()

# =========================
# 音声出力・入力関数
# =========================
def speak(text: str):
    """指定したテキストを音声で読み上げる"""
    engine.say(text)
    engine.runAndWait()


def recognize_speech(timeout_seconds=180) -> str:
    """
    音声を認識して文字列を返す。
    timeout_seconds: 音声入力の待機を何秒まで続けるか(リッスン時間の上限)
    """
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print(f"音声入力を待機しています... 最大{timeout_seconds}秒")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=timeout_seconds, phrase_time_limit=timeout_seconds)
        except sr.WaitTimeoutError:
            print("指定時間内に音声が入力されませんでした。")
            return ""

    # Google Web Speech API などを使って文字起こし
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
# DB操作系関数
# =========================
def fetch_tasks():
    """
    Supabaseから毎日通知するタスクを取得。
    ここでは「recurrence = 'everyday'」を対象に想定。
    scheduled_time は "HH:MM:SS" 形式で入っていることを想定。
    """
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").eq("user_id", CURRENT_USER_ID).execute()
    return response.data if response.data else []
    print(response.data)


def mark_task_completed(task_id: str):
    """
    task_completions テーブルへレコードを挿入し、タスク完了を記録する。
    """
    now_str = datetime.datetime.now().isoformat()
    data = {
        "task_id": task_id,
        "user_id": CURRENT_USER_ID,
        "completed_at": now_str  # タイムスタンプをISO8601文字列で
    }
    try:
        response = supabase.table("task_completions").insert(data).execute()
        if response.data:
            print(f"タスク({task_id})を完了登録しました: {response.data}")
            speak("タスクを完了登録しました。お疲れ様です。")
        else:
            print("タスク完了登録に失敗しました:", response)
            speak("タスク完了の登録に失敗しました。")
    except Exception as e:
        print("DB登録でエラーが発生しました:", str(e))
        speak("タスク完了の登録でエラーが発生しました。")


# =========================
# 通知後に完了を待ち受ける処理
# =========================
def notify_and_wait_for_completion(task: dict):
    """
    タスクを音声で通知したあと、180秒以内にユーザーが
    「完了した」「やったよ」などと話したら completed_at をセット。
    """
    title = task["title"]
    task_id = task["id"]
    scheduled_time = task.get("scheduled_time", "??:??:??")

    # 1) タスク通知
    speak(f"タスクの時間です。{title} をお願いします。")
    print(f"[通知] 毎日 {scheduled_time} に {title} の時間です。")

    # 2) 完了の音声入力を待ち受ける
    speak("完了したら '完了したよ' と言ってください。")
    user_input = recognize_speech(timeout_seconds=180)

    # 3) 入力内容に「完了」「やった」「できた」などが含まれていたら完了登録
    if any(keyword in user_input for keyword in ["完了", "やった", "できた", "done"]):
        mark_task_completed(task_id)
    else:
        print("完了ワードが検出されませんでした。")
        speak("完了が確認できませんでした。また後でチェックしますね。")


# =========================
# スケジューラ関連
# =========================
#
def schedule_notifications():
    """ 毎日指定時間に通知をスケジュール """
    tasks = fetch_tasks()
    for task in tasks:
        title = task["title"]
        scheduled_time = task["scheduled_time"]  # 形式: "21:00:00"

        # 時間を分解
        hour, minute, _ = map(int, scheduled_time.split(":"))

        # スケジュール設定
        # schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(speak, title)
        schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(notify_and_wait_for_completion, task)

        print(f"毎日 {hour:02d}:{minute:02d} に『{title}』を通知")


def run_scheduler():
    """
    スケジューラを走らせ続ける。
    30秒ごとに schedule.run_pending() を実行。
    """
    schedule_notifications()  # スケジュールを初期設定
    while True:
        schedule.run_pending()
        time.sleep(30)  # 30秒待って再チェック


# =========================
# エントリポイント
# =========================
if __name__ == "__main__":
    run_scheduler()
