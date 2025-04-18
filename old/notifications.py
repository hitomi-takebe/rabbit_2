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

#タスクの完了登録がうまくいってない

def fetch_tasks():
    """
    Supabaseから、毎日通知するタスク（recurrenceが'everyday'かつ自分のタスク）を取得する。
    """
    response = supabase.table("tasks").select("*").eq("recurrence", "everyday").eq("user_id", CURRENT_USER_ID).execute()
    return response.data if response.data else []

def confirm_task_completion(input_text: str) -> bool:
    few_shot_prompt = """
あなたはタスク完了確認アシスタントです。
以下のユーザー発話が、タスクを完了したことを意味するか判定し、JSON形式で回答してください。

入力されたユーザー発話に基づき、以下の形式のJSONのみを出力してください:
{{"status": "<Completed | NotCompleted>"}}


=== FEW-SHOT EXAMPLES ===

[例1]
ユーザー発話:「完了」、「完了しました」、「やりました」
出力: 
{{
"status": "Completed"
}}

[例2]
ユーザー発話:「まだです」
出力: 
{{
"status": "NotCompleted"
}}

[例3]
ユーザー発話:「終わりました！」
出力: 
{{
"status": "Completed"
}}

[例4]
ユーザー発話:「ちょっと待ってください」
出力: 
{{
"status": "NotCompleted"
}}

=== END OF EXAMPLES ===

以下のユーザー発話: 「{input_text}」
この発話の意図を判定し、**JSON形式** で答えてください。

"""

    prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
    final_prompt = prompt_template.format(input_text=input_text)
    print("AIに入力された文章：",final_prompt)
    response = chat_model.invoke(final_prompt)
    cleaned_content = response.content.strip().strip("```").strip()
    print("AIから出力された文章：", response.content)
    print("AIから出力された文章を綺麗にしたもの：",cleaned_content)

    try:
        result = json.loads(cleaned_content)    # JSON形式の文字列を辞書型に変換
        print("statusの値:", result)    # statusの値を確認
        intent = result.get("status", "NotCompleted") #statusの値がない場合はNotCompletedを返す
        if intent in ["Completed", "NotCompleted"]: # Completed または NotCompletedの場合はそのまま返す
            return intent
        return "NotCompleted"   # それ以外の場合は NotCompleted を返す
    except json.JSONDecodeError:    # JSON形式でない場合はNotCompletedを返す
        print("AIの応答をJSONとして解析できませんでした:", cleaned_content)
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

    status = confirm_task_completion(user_input)
    if status == "Completed":
        mark_task_completed(task_id)
    else:
        print("完了ワードが検出されませんでした。")
        speak("完了が確認できませんでした。また今度頑張ろうね。")
        handle_incomplete_task(task_id)
        


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

def handle_incomplete_task(task_id: str):
    """
    タスクが完了しなかった場合の処理
    例: その旨を伝え、別のリマインドを行う（ここでは単に通知失敗の旨を伝える）
    """
    print(f"タスク({task_id})は完了していませんでした。")
    speak("タスクが完了していないようです。後ほど再度通知します。")
    # ここで必要に応じて、再通知のための処理を追加できます。


# notifications.py
# import json
# import datetime
# from langchain.prompts import PromptTemplate
# from config import chat_model
# from speech import recognize_speech


# def confirm_task_completion(input_text: str) -> bool:
#     """
#     ユーザーの発話を元にタスクが完了したかをAIに判定させる関数。
#     Completed なら True、それ以外は Falseを返す。
#     """
#     few_shot_prompt = """
# あなたはタスク完了確認アシスタントです。
# 以下のユーザー発話が、タスクを完了したことを意味するか判定し、JSON形式で回答してください。

# 出力形式:
# {"status": "Completed" または "NotCompleted"}

# === FEW-SHOT EXAMPLES ===

# [例1]
# 入力:「完了したよ」
# 出力: {"status": "Completed"}

# [例2]
# ユーザー発話:「まだです」
# 出力:
# {"status": "NotCompleted"}

# [例3]
# ユーザー発話:「終わりました！」
# 出力:
# {"status": "Completed"}

# [例4]
# ユーザー発話:「ちょっと待ってください」
# 出力:
# {"status": "NotCompleted"}

# === END OF EXAMPLES ===

# ユーザー発話: "{input_text}"
# """

#     prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
#     final_prompt = prompt_template.format(input_text=input_text)
#     print("AIに入力された文章：",final_prompt)
#     response = chat_model.invoke(final_prompt)
#     cleaned_content = response.content.strip().strip("```").strip()
#     print("AIから出力された文章：", response.content)
#     print("AIから出力された文章を綺麗にしたもの：",cleaned_content)


#     try:
#         result = json.loads(cleaned_content)
#         print("intentの値:", result)
#         return result["status"] == "Completed"
#     except json.JONDecodeError:
#         print("AIの応答をJSONとして解析できませんでした:", response.content)
#         return False
