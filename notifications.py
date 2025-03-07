# notifications.py

import json
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import datetime
import time
from audio import speak, recognize_speech
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


# ChatOpenAI クライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

def fetch_tasks():
    """
    Supabaseから、毎日通知するタスク（recurrenceが'everyday'かつ自分のタスク）を取得する。
    """
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").eq("user_id", CURRENT_USER_ID).execute()
    return response.data if response.data else []

def confirm_completion(user_text: str) -> bool:
    """
    FEW-SHOT プロンプトを用いて、ユーザーの発話がタスク完了の通知であるかを判定する関数。
    返答は "Completed" または "NotCompleted" の単語のみで出力してください。

    例:
    入力: "完了しました"
    出力: Completed

    入力: "まだです"
    出力: NotCompleted
    """
    few_shot_prompt = """
あなたはタスク管理アシスタントです。以下のルールに従って、ユーザーの発話がタスク完了を意味するか判定してください。
- タスク完了を意味する場合は "Completed" と出力してください。
- それ以外の場合は "NotCompleted" と出力してください。

例:
入力: "完了しました"、 "終わったよ"、 "完了したよ"、 "できたよ"、"やったよ"、"終わりました"
出力: Completed


入力: "まだです"、 ”まだだよ”、 ”いや”、 ”やりたくない”、 ”むり”
出力: NotCompleted

以下のユーザー発話: "{input_text}"
この発話の意図を判定し、**JSON形式** で答えてください。
"""
    prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
    final_prompt = prompt_template.format(input_text=user_text)
    response = chat_model.invoke(final_prompt)
    # 余計なバッククォートや空白、複数行があれば最初の行を抽出
    output = response.content.strip().strip("```").strip().splitlines()[0].strip()
    print(f"認識した完了判定応答: '{output}'")  # デバッグ用
    if output == "Completed":
        return True
    else:
        return False

def notify_and_wait_for_completion(task: dict):
    """
    タスク通知機能:
    タスクの予定時刻に通知し、ユーザーから完了報告（例："完了したよ"）を待つ。
    """
    title = task["title"]
    task_id = task["id"]
    scheduled_time = task.get("scheduled_time", "??:??:??")
    speak(f"タスクの時間です。{title} をお願いします。")
    print(f"[通知] 毎日 {scheduled_time} に {title} の時間です。")
    speak("完了したら『完了したよ』などと言ってください。")
    user_input = recognize_speech(timeout_seconds=180)
    print(f"認識結果: '{user_input}'")  # 取得された発話の確認

    if confirm_completion(user_input):
        mark_task_completed(task_id)
    else:
        print("完了ワードが検出されませんでした。")
        speak("完了が確認できませんでした。また後でチェックしますね。")

def mark_task_completed(task_id: str):
    """
    タスク完了の報告を DB に登録する。
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

def run_task_notifications():
    """定期的にタスク通知をチェックし実行するループ"""
    while True:
        tasks = fetch_tasks()
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        for task in tasks:
            if task["scheduled_time"] == current_time:
                notify_and_wait_for_completion(task)
                break  # 1回のループで1つのタスクのみ通知する
        time.sleep(1)
