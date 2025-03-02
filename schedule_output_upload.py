import schedule
import time
import pyttsx3
from supabase import create_client, Client
import datetime
from langchain_openai import ChatOpenAI
import random  # 乱数生成モジュールを追加

# OpenAI APIキーを直接設定
OPENAI_API_KEY = ""

# Supabase の設定
SUPABASE_URL = ""
SUPABASE_KEY = ""
CURRENT_USER_ID = ""  # 仮のユーザーID
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ChatOpenAI（LangChain）クライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

# 音声エンジンの初期化
engine = pyttsx3.init()

def speak(text):
    """ 指定したテキストを音声で読み上げる """
    engine.say(text)
    engine.runAndWait()

def fetch_tasks():
    """ Supabaseから毎日通知するタスクを取得 """
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").execute()
    return response.data if response.data else []

def generate_cute_message(task_title, hour, minute):
    """ OpenAIを使って可愛らしい通知メッセージを生成 """
    time_str = f"{hour:02d}:{minute:02d}"
    prompt = f"{time_str}だよ。タスクは『{task_title}』だよ。可愛らしい女の子が話すような感じで、毎回違う言い方で、3種類の短い通知メッセージを考えて。"

    response = chat_model.predict(prompt)
    messages = response.strip().split('\n') # 改行で分割してメッセージリストにする
    messages = [msg.strip() for msg in messages if msg.strip()] # 空行を削除

    return messages

def schedule_notifications():
    """ 毎日指定時間に通知をスケジュール """
    tasks = fetch_tasks()
    for task in tasks:
        title = task["title"]
        scheduled_time = task["scheduled_time"]  # 形式: "21:00:00"

        # 時間を分解
        hour, minute, _ = map(int, scheduled_time.split(":"))

        # OpenAIでメッセージ生成
        cute_messages = generate_cute_message(title, hour, minute)

        if cute_messages: # メッセージが生成された場合のみスケジュール
            # スケジュール設定 (毎回違うメッセージをランダムに選択)
            schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(
                lambda task_messages=cute_messages: speak(random.choice(task_messages)) # lambda関数でメッセージを固定
            )
            print(f"毎日 {hour:02d}:{minute:02d} に『{title}』を通知 (可愛らしいメッセージ)")
        else:
             print(f"毎日 {hour:02d}:{minute:02d} に『{title}』を通知 (メッセージ生成失敗)")


def run_scheduler():
    """ スケジューラを実行し続ける """
    schedule_notifications()  # 最初にスケジュールをセット
    while True:
        schedule.run_pending()  # タスク実行
        time.sleep(30)  # 30秒ごとにチェック

if __name__ == "__main__":
    run_scheduler()