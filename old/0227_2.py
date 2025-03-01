import datetime
import speech_recognition as sr
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from jmea_tix import TimexParser
import pendulum

# 環境変数の読み込み
load_dotenv()
SUPABASE_URL = ""
SUPABASE_KEY = ""
CURRENT_USER_ID = ""  # 仮のユーザーID
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ja-timex のパーサー
timex_parser = TimexParser()

def recognize_speech(prompt):
    """音声入力を受け付ける"""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print(prompt)
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        print("認識結果:", text)
        return text
    except sr.UnknownValueError:
        print("音声を認識できませんでした。もう一度お願いします。")
        return recognize_speech(prompt)  # 再試行
    except sr.RequestError:
        print("音声認識サービスに接続できませんでした。")
        return None

def parse_datetime(input_text):
    """音声認識された日時をパースして 'YYYY-MM-DD HH:MM:SS' 形式に変換"""
    # now = pendulum.now("Asia/Tokyo")  # 現在時刻を取得（日本時間）
    # timezone = pendulum.timezone("Asia/Tokyo")  # pendulumのタイムゾーンオブジェクト

    try:
        tokyo_tz = pendulum.timezone("Asia/Tokyo")  # ← タイムゾーンを明示的に指定
        now = pendulum.now(tokyo_tz)  
        timex_parser = TimexParser()  # TimexParserを初期化
        parsed_time = timex_parser.parse(input_text)  # 文字列を解析

        if not parsed_time:
            raise ValueError("日時の解析に失敗")
        
        # 一番最初に見つかった日時情報を取得
        dt = parsed_time[0].to_datetime(now)
        return dt.to_datetime_string()  # 'YYYY-MM-DD HH:MM:SS' 形式に変換
    except Exception as e:
        print(f"日時の解析に失敗しました: {e}")
        return None



def insert_task():
    """Supabaseのtasksテーブルにタスクを登録する"""
    title = recognize_speech("タスクのタイトルを教えてください...")
    if not title: return

    description = recognize_speech("タスクの詳細を教えてください...")
    if not description: return

    while True:
        scheduled_time_text = recognize_speech("タスクの予定時刻を教えてください（例: 今日の9時、明日の18時、22:00）...")
        scheduled_time = parse_datetime(scheduled_time_text)
        if scheduled_time:
            break  # 変換成功したらループを抜ける

    recurrence = recognize_speech("繰り返し設定を教えてください（なし、毎日、平日、週末）...")
    if not recurrence: return

    now = datetime.datetime.now().isoformat()
    task_data = {
        "user_id": CURRENT_USER_ID,
        "title": title,
        "description": description,
        "scheduled_time": scheduled_time,
        "recurrence": recurrence,
        "next_occurrence": scheduled_time if recurrence != "なし" else now
    }
    
    try:
        response = supabase.table("tasks").insert(task_data).execute()
        if response.data:
            print("タスクを追加しました:", response.data)
        else:
            print("データの挿入に失敗しました:", response)
    except Exception as e:
        print("エラーが発生しました:", str(e))

if __name__ == "__main__":
    insert_task()
