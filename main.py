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
# 🔥 スレッドセーフなロックを作成
speech_lock = threading.Lock()

def speak(text: str):
    """指定したテキストを音声で読み上げる（スレッドセーフ）"""
    with speech_lock:  # 🔥 他のスレッドと競合しないようにロック
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()

# =========================
# 音声入力関数
# =========================
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
# ユーザーの意図を判定する関数
# =========================
def extract_intent_info(input_text: str) -> str:
    """
    FEW-SHOTプロンプトを使い、ユーザーの発話を3つのカテゴリに分類する。
    意図の種類：
    - "TaskRegistration" → ユーザーがタスクを登録したい場合
    - "SiriChat" → ユーザーが「Hi Siri」と話しかけた場合
    - "Silent" → 無音または認識できなかった場合

    出力は JSON 形式:
    {
      "intent": "TaskRegistration"  // または "SiriChat", "Silent"
    }
    """

    few_shot_prompt = """
あなたは音声アシスタントです。ユーザーの発話を聞き、その意図を以下の3つのカテゴリのいずれかに分類してください。

1. **TaskRegistration**: ユーザーがタスクを登録したい（例：「タスクを登録」「タスク追加」など）
2. **SiriChat**: ユーザーが「Hi Siri」と話しかけた（例：「Hi Siri」「Hey Siri」など）
3. **Silent**: ユーザーが無言だった、または認識できなかった

出力は次の JSON 形式で行ってください：
{{
  "intent": "<TaskRegistration | SiriChat | Silent>"
}}

=== FEW-SHOT EXAMPLES ===

[Example 1]
User: "タスクを登録したい"
Assistant:
{{
  "intent": "TaskRegistration"
}}

[Example 2]
User: "Hi Siri"
Assistant:
{{
  "intent": "SiriChat"
}}

[Example 3]
User: "Hey Siri、今日の天気は？"
Assistant:
{{
  "intent": "SiriChat"
}}

[Example 6]
User: "今日はいい天気ですね"
Assistant:
{{
  "intent": "Silent"
}}

[Example 7]
User: "お腹すいた"
Assistant:
{{
  "intent": "Silent"
}}

=== END OF EXAMPLES ===

以下の発話：「{input_text}」  
この発話の意図を判定し、必ず **JSON形式** で答えてください。
"""
    
    # プロンプトを構築
    prompt_template = PromptTemplate(
        input_variables=["input_text"],
        template=few_shot_prompt
    )
    final_prompt = prompt_template.format(input_text=input_text)

    # OpenAI API にリクエスト
    response = chat_model.invoke(final_prompt)

    # JSON解析
    try:
        result = json.loads(response.content.strip())
        intent = result.get("intent", "Silent")  # デフォルトを "Silent" に設定
        return intent if intent in ["TaskRegistration", "SiriChat"] else "Silent"
    except (json.JSONDecodeError, AttributeError):
        print("intent解析に失敗しました。レスポンス:", response.content)
        return "Silent"



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
    """ タスク通知モード """
    print("タスク通知を開始します。")
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
    text_for_task = recognize_speech(timeout_seconds=120)  # ここでは数値のみを渡す

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
# Siri風雑談モード
# =========================
def siri_chat():
    """ Siri風の雑談モード """
    speak("Siriモードです。何かお話ししますか？")

# =========================
# メインのループ
# =========================
import threading

def background_listen():
    """ 音声認識を別スレッドで実行する """
    while True:
        user_text = recognize_speech(timeout_seconds=5)  # 5秒ごとに音声認識
        if user_text:
            process_user_input(user_text)

def process_user_input(user_text):
    """ 音声認識の結果を処理し、適切なモードを実行 """
    intent = extract_intent_info(user_text)
    print(f"推定Intent: {intent}")

    if intent == "TaskRegistration":
        insert_task()  # タスク登録モード
    elif intent == "SiriChat":
        siri_chat()  # Siri風雑談モード
    else:
        print("無効な発話。何もしません。")

def main_loop():
    """ タスク通知を最優先しながら、音声認識を非同期で待機 """
    # 🎤 **音声認識をバックグラウンドスレッドで開始**
    listen_thread = threading.Thread(target=background_listen, daemon=True)
    listen_thread.start()

    while True:
        tasks = fetch_tasks()  # 🔥 最新のタスクを取得
        current_time = datetime.datetime.now().strftime("%H:%M:%S")

        # 🚀 **タスク通知がある場合、最優先で実行**
        for task in tasks:
            if task["scheduled_time"] == current_time:
                notify_and_wait_for_completion(task)
                break  # 1回のループで1つのタスクのみ通知する

        time.sleep(1)  # 無駄なCPU負荷を避ける


# =========================
# メイン実行
# =========================
if __name__ == "__main__":
    main_loop()
