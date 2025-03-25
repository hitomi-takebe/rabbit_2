# notifications.py

import sys
import os

# # 一個上のディレクトリをsys.pathに追加
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import datetime
import time
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import datetime
import time
from audio import speak, recognize_speech
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase
# from notifications import mark_task_completed, handle_incomplete_task

# ChatOpenAI クライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

def fetch_tasks():
    """
    Supabaseから、毎日通知するタスク（recurrenceが'everyday'かつ自分のタスク）を取得する。
    """
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").eq("user_id", CURRENT_USER_ID).execute()
    return response.data if response.data else []

def confirm_task_completion(input_text: str) -> bool:
    """
    FEW-SHOT プロンプトを用いて、ユーザーの発話がタスク完了を意味するか判定する関数。
    出力は以下の形式の JSON 形式で返してください:
    {"status": "<Completed | NotCompleted>"}
    """
    few_shot_prompt = """
あなたはタスク完了確認アシスタントです。
以下のユーザー発話が、タスク完了を意味するか判定し、JSON形式で回答してください。

出力形式:
{{"status": "<Completed | NotCompleted>"}}

=== FEW-SHOT EXAMPLES ===

[例1]
ユーザー発話:「完了したよ」
出力: 
{{"status": "Completed"}}

[例2]
ユーザー発話:「まだです」
出力: 
{{"status": "NotCompleted"}}

[例3]
ユーザー発話:「終わりました！」
出力: 
{{"status": "Completed"}}

[例4]
ユーザー発話:「ちょっと待ってください」
出力: 
{{"status": "NotCompleted"}}

=== END OF EXAMPLES ===

以下のユーザー発話: "{input_text}"
"""
    prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
    final_prompt = prompt_template.format(input_text=input_text)
    print("AIに入力された文章：", final_prompt)
    response = chat_model.invoke(final_prompt)
    cleaned_content = response.content.strip().strip("```").strip()
    print("AIから出力された文章：", response.content)
    print("AIから出力された文章を綺麗にしたもの：", cleaned_content)

    try:
        result = json.loads(cleaned_content)
        status = result.get("status", "NotCompleted")
        return status if status in ["Completed", "NotCompleted"] else "NotCompleted"
    
        # print("statusの値:", result)
        # # 期待するキーは "status" です
        # intent = result.get("status", "NotCompleted")
        # return intent == "Completed"
    except json.JSONDecodeError:
        print("AIの応答をJSONとして解析できませんでした:", cleaned_content)
        return "NotCompleted"

# 旧mark_task_completed
def record_task_completion(task_id: str, is_completed: bool):
    """
    タスク完了の報告を DB に登録する処理。
    """
    now_str = datetime.datetime.now().isoformat()
    data = {
        "task_id": task_id,
        "user_id": CURRENT_USER_ID,
        "is_completed": is_completed,
        "created_at": now_str
    }
    try:
        response = supabase.table("task_completions").insert(data).execute()
        if response.data:
            print(f"[DB] タスク({task_id}) を記録しました（完了: {is_completed}）")
            speak("完了登録しました。" if is_completed else "未完了として記録しました。")
        else:
            print("[DB] 登録に失敗:", response)
            speak("タスクの登録に失敗しました。")
    except Exception as e:
        print("DB登録でエラーが発生しました:", str(e))
        speak("タスク完了の登録でエラーが発生しました。")

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
    print(f"認識結果: '{user_input}'")

    status = confirm_task_completion(user_input)
    is_completed = status == "Completed"
    record_task_completion(task_id, is_completed)

    if not is_completed:
        speak("完了が確認できませんでした。また今度頑張ろうね。")
        handle_incomplete_task(task_id)

def handle_incomplete_task(task_id: str):
    """
    未完了時の処理（通知・ログ記録など）
    """
    print(f"タスク({task_id}) は未完了でした。")
    # 再通知や記録処理などをここに追加できます

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

if __name__ == "__main__":
    run_task_notifications()
