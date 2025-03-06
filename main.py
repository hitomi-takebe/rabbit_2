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


# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


# Supabaseクライアントの初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ChatOpenAIクライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

# pyttsx3の音声エンジン初期化（ここではグローバル変数として利用）
engine = pyttsx3.init()


# =========================
# 音声合成 (TTS) 関数
# =========================
def speak(text: str):
    """指定したテキストを音声で読み上げる"""
    engine.say(text)
    engine.runAndWait()


# =========================
# 音声入力関数
# =========================
def recognize_speech(timeout_seconds=180) -> str:
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
# タスク登録関連
# =========================
def extract_intent_info(input_text: str) -> str:
    """
    FEW-SHOTプロンプトを使い、入力文章が「タスク登録かどうか」を判定。
    - "TaskRegistration" or "Others" を返す。

    *Pythonのフォーマット文字列と衝突しないよう、JSONの { } は {{ }} でエスケープ。
    """
    few_shot_prompt = """
あなたはユーザーの文章を読み取り、その意図を判断するアシスタントです。
可能な意図は以下の2つのみです:
1. TaskRegistration: ユーザーがタスクを登録しようとしている
2. Others: タスク登録とは無関係な内容

出力は以下の形式のJSON:
{{
  "intent": "TaskRegistration"  // または "Others"
}}

=== FEW-SHOT EXAMPLES ===

[Example 1]
User: "タスクを登録したいんだけど"
Assistant:
{{
  "intent": "TaskRegistration"
}}

[Example 2]
User: "今日はいい天気ですね"
Assistant:
{{
  "intent": "Others"
}}

=== END OF EXAMPLES ===

以下の文章: 「{input_text}」
を判定し、必ず上記JSON形式のみで答えてください。
"""
    prompt_template = PromptTemplate(
        input_variables=["input_text"],
        template=few_shot_prompt
    )
    final_prompt = prompt_template.format(input_text=input_text)

    response = chat_model.invoke(final_prompt)

    # JSON解析
    try:
        result = json.loads(response.content.strip())
        intent = result.get("intent", "Others")
        if intent in ["TaskRegistration", "Others"]:
            return intent
        return "Others"
    except (json.JSONDecodeError, AttributeError):
        print("intent解析に失敗しました。レスポンス:", response.content)
        return "Others"


def always_on_loop():
    """
    - プログラムはループ内でずっとマイクを待ち受ける
    - "タスクを登録" と言うなどでタスク登録の意図と判定されたら insert_task() を呼び出す
    - "シャットダウン" があればプログラム終了する
    """
    print("起動しました。いつでも『タスクを登録したい』『タスクを登録する』などと言ってください。シャットダウンで完全終了します。")
    speak("起動しました。いつでも『タスクを登録したい』や『タスクを登録する』などと言ってください。シャットダウンで完全終了します。")

    while True:
        user_text = recognize_speech()  # プロンプトなしで待機
        if not user_text:
            continue  # 発話が認識できなかった場合はループの先頭に戻る

        # キーワードチェック（各キーワードに対してin user_textを適用）
        if ("シャットダウン" in user_text or 
            "さようなら" in user_text):
            speak("プログラムを終了します。")
            print("プログラムを終了します。")
            break

        # FEW-SHOTでIntent判定
        intent = extract_intent_info(user_text)
        print("推定Intent:", intent)

        if intent == "TaskRegistration":
            insert_task()
        else:
            speak("タスク登録以外の会話ですね。特に処理は行いません。")
            print("→ Others")


# =========================
# タスクの情報を通知して完了登録
# =========================

def fetch_tasks():
    """
    Supabaseから毎日通知するタスクを取得。
    ここでは、recurrenceが'everyday'かつCURRENT_USER_IDのタスクを取得することを想定。
    タスクのscheduled_timeは "HH:MM:SS" 形式とする。
    """
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").eq("user_id", CURRENT_USER_ID).execute()
    return response.data if response.data else []


def schedule_notifications():
    """
    Supabaseから取得したタスク情報に基づき、毎日指定時間にリマインド通知をスケジュールする。
    """
    tasks = fetch_tasks()
    for task in tasks:
        title = task["title"]
        scheduled_time = task["scheduled_time"]  # 例: "21:00:00"
        
        # 時間を分解
        hour, minute, _ = map(int, scheduled_time.split(":"))
        
        # 毎日指定時刻に notify_and_wait_for_completion を実行
        schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(notify_and_wait_for_completion, task)
        
        print(f"毎日 {hour:02d}:{minute:02d} に『{title}』を通知")

def run_scheduler():
    """
    スケジューラを走らせ続ける。
    30秒ごとに schedule.run_pending() を実行して、タスクリマインドをチェックする。
    """
    # schedule_notifications()  # タスクごとにリマインドスケジュールを設定
    while True:
        schedule_notifications()  # 🔥 最新のタスクを取得しスケジュール更新
        schedule.run_pending()
        time.sleep(30)

def notify_and_wait_for_completion(task: dict):
    """
    タスクの予定時刻になったらタスク内容を通知し、完了の音声入力（例："完了したよ"）を受け付け、
    完了が確認できればタスク完了登録を行う。
    """
    title = task["title"]
    task_id = task["id"]
    scheduled_time = task.get("scheduled_time", "??:??:??")
    
    # 1) タスク通知
    speak(f"タスクの時間です。{title} をお願いします。")
    print(f"[通知] 毎日 {scheduled_time} に {title} の時間です。")
    
    # 2) 完了の音声入力を待つ
    speak("完了したら『完了したよ』などと言ってください。")
    user_input = recognize_speech(timeout_seconds=180)
    
    # 3) 完了キーワードが含まれていたら完了登録
    if any(keyword in user_input for keyword in ["完了", "やった", "できた", "done"]):
        mark_task_completed(task_id)
    else:
        print("完了ワードが検出されませんでした。")
        speak("完了が確認できませんでした。また後でチェックしますね。")

def mark_task_completed(task_id: str):
    """
    task_completions テーブルへレコードを挿入し、タスク完了を記録する。
    """
    now_str = datetime.datetime.now().isoformat()
    data = {
        "task_id": task_id,
        "user_id": CURRENT_USER_ID,
        "completed_at": now_str
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

def extract_intent_info(input_text: str) -> str:
    """
    FEW-SHOTプロンプトを使い、入力文章が「タスク登録かどうか」を判定。
    - "TaskRegistration" or "Others" を返す。

    *Pythonのフォーマット文字列と衝突しないよう、JSONの { } は {{ }} でエスケープ。
    """
    few_shot_prompt = """
あなたはユーザーの文章を読み取り、その意図を判断するアシスタントです。
可能な意図は以下の2つのみです:
1. TaskRegistration: ユーザーがタスクを登録しようとしている
2. Others: タスク登録とは無関係な内容

出力は以下の形式のJSON:
{{
  "intent": "TaskRegistration"  // または "Others"
}}

=== FEW-SHOT EXAMPLES ===

[Example 1]
User: "タスクを登録したいんだけど"
Assistant:
{{
  "intent": "TaskRegistration"
}}

[Example 2]
User: "今日はいい天気ですね"
Assistant:
{{
  "intent": "Others"
}}

=== END OF EXAMPLES ===

以下の文章: 「{input_text}」
を判定し、必ず上記JSON形式のみで答えてください。
"""
    prompt_template = PromptTemplate(
        input_variables=["input_text"],
        template=few_shot_prompt
    )
    final_prompt = prompt_template.format(input_text=input_text)

    response = chat_model.invoke(final_prompt)

    # JSON解析
    try:
        result = json.loads(response.content.strip())
        intent = result.get("intent", "Others")
        if intent in ["TaskRegistration", "Others"]:
            return intent
        return "Others"
    except (json.JSONDecodeError, AttributeError):
        print("intent解析に失敗しました。レスポンス:", response.content)
        return "Others"

# =========================
# 5. タスク詳細を抜き出す関数
# =========================
def extract_task_info(input_text: str) -> dict:
    """
    タスクのタイトル + 予定時刻 を抽出
    出力例:
    {
      "title": "お風呂に入る",
      "scheduled_time": "21:00:00"  // または null
    }

    *ここでも { } を {{ }} にエスケープ
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
        もし時刻が含まれていなければ "scheduled_time": null としてください。
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


# =========================
# 6. タスク登録 (DB挿入) + 音声応答
# =========================
def insert_task():
    """
    タスクの詳細を音声で取得 → OpenAIで解析 → SupabaseのDBにINSERT
    """
    speak("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")  # プロンプトを音声で伝える
    text_for_task = recognize_speech(timeout_seconds=180)  # ここでは数値のみを渡す

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
# メイン実行
# =========================
if __name__ == "__main__":
    import threading

    # 🔥 スケジューラーを別スレッドで実行（定期的にタスクを更新）
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()


    # 音声認識のループも開始
    always_on_loop()
