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
from datetime import datetime, timedelta
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

# タスク完了率を取得する関数
def get_task_completion_rate(task_id: str, user_id: str, days: int = 7) -> float:
    """
    過去 `days` 日間のタスク達成率（task_id かつ user_id）を計算
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = supabase.table("task_completions")\
        .select("is_completed")\
        .eq("task_id", task_id)\
        .eq("user_id", user_id)\
        .gte("created_at", since_date)\
        .execute()
    records = res.data or []
    if not records:
        return 0.0
    total = len(records)
    completed = sum(1 for r in records if r.get("is_completed") is True)
    return completed / total

# タスク完了率を取得する関数
def get_overall_completion_rate(user_id: str, days: int = 7) -> float:
    """
    過去 `days` 日間の全体のタスク達成率（user_idベース）を計算
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = supabase.table("task_completions")\
        .select("is_completed")\
        .eq("user_id", user_id)\
        .gte("created_at", since_date)\
        .execute()
    records = res.data or []
    if not records:
        return 0.0
    total = len(records)
    completed = sum(1 for r in records if r.get("is_completed") is True)
    return completed / total

# 発言内容を達成度に応じて合成する関数
def get_motivational_message(title: str, scheduled_time: str, task_rate: float, overall_rate: float) -> str:
    """
    達成率に応じてテンションを変えるメッセージを返す
    """
    # base = f"{scheduled_time} に {title} の時間だよ！"
    # if task_rate >= 0.8 and overall_rate >= 0.8:
    #     return f"今日も絶好調！{base}このタスクの達成率は{task_rate * 100:.0f}％!完了したら『完了したよ』と言ってね。"
    # elif task_rate >= 0.5 or overall_rate >= 0.5:
    #     return f"コツコツ続けてるね。{base}このタスクの達成率は{task_rate * 100:.0f}％!完了したら『完了したよ』と言ってね。"
    # elif task_rate > 0 or overall_rate > 0:
    #     return f"たまには {title} をやってみよう！応援してるよ。{base}"
    # else:
    #     return f"今日は気合を入れて {title} をやってみよう！{base}完了したら『完了したよ』などと言ってね。"

    """
    OpenAI にプロンプトを送り、自然なリマインドメッセージを生成する
    """
    prompt = f"""
あなたは、優しくてちょっととぼけたウサギのキャラクターです。
ユーザーにタスクを思い出させる、自然で押し付けがましくない言い回しを1文で作ってください。

## 条件
- タスク名: {title}
- タスクの予定時刻: {scheduled_time}
- このタスクの直近の達成率: {task_rate:.0%}
- ユーザー全体の最近の達成率: {overall_rate:.0%}

## 出力形式
自然な話し言葉の1文のみを返してください。ただしあくまでもタスクをすることを促してください。（例:「9:00だね。もう散歩した？気分転換になるかも〜」「ごはん…食べた？いや、夢の中で食べたのかも…」「23:00だね。そろそろおふとんの時間かな？ぼくもう先にゴロンしてるね。」）
""".strip()

    response = chat_model.invoke(prompt)
    return response.content.strip()

def confirm_task_completion(input_text: dict, task_title: str) -> str:
    """
    タスクのタイトルに応じて、ユーザーの発話が完了を意味するかどうかをAIに判断させる。
    """
    user_text = input_text.get("text", "").strip().lower()

    prompt = f"""
あなたは、優しくてちょっととぼけたウサギのアシスタントです。
以下の条件で、ユーザーが「タスクを完了したかどうか」を判定し、必ずJSONで返してください。

## 出力形式
{{"status": "<Completed | NotCompleted>"}}

## タスク名
{task_title}

## ユーザーの発話
「{user_text}」

## 判定のルール
- 完了を意味する自然な表現（例：「やった」「終わった」「済んだ」「入った」など）は Completed とする
- 「まだ」「あとで」「これから」などは NotCompleted とする
"""
    response = chat_model.invoke(prompt)
    cleaned_content = response.content.strip().strip("```").strip()
    print("完了判定プロンプト応答:", cleaned_content)

    try:
        result = json.loads(cleaned_content)
        return result.get("status", "NotCompleted")
    except json.JSONDecodeError:
        return "NotCompleted"

# 旧mark_task_completed
def record_task_completion(task_id: str, is_completed: bool):
    """
    タスク完了の報告を DB に登録する処理。
    """
    now_str = datetime.now().isoformat()
    data = {
        "task_id": task_id,
        "user_id": CURRENT_USER_ID,
        "is_completed": is_completed,
        "created_at": now_str
    }
    try:
        response = supabase.table("task_completions").insert(data).execute()
        if response.data:
            print(f"[DB] タスク({task_id}) を記録したよ（完了: {is_completed}）")
            speak("完了登録したよ。" if is_completed else "未完了として記録したよ。")
        else:
            print("[DB] 登録に失敗:", response)
            speak("タスクの登録に失敗しちゃった。")
    except Exception as e:
        print("DB登録でエラーが発生しました:", str(e))
        speak("タスク完了の登録でエラーが発生したみたい。")

def notify_and_wait_for_completion(task: dict):
    """
    タスク通知機能:
    タスクの予定時刻に通知し、ユーザーから完了報告（例："完了したよ"）を待つ。
    """
    title = task["title"]
    task_id = task["id"]
    scheduled_time = task.get("scheduled_time", "??:??:??")

    task_rate = get_task_completion_rate(task_id, CURRENT_USER_ID)
    overall_rate = get_overall_completion_rate(CURRENT_USER_ID)
    print(f"[達成率] タスク別: {task_rate:.0%}, 全体: {overall_rate:.0%}")

    # 🐰 タスクのリマインドメッセージ
    message = get_motivational_message(title,scheduled_time, task_rate, overall_rate)
    print(message)
    speak(message)

    # 🎤 最初の音声入力（タスクへの返答）
    user_input = recognize_speech(timeout_seconds=180)
    user_text = user_input.get("text", "").strip() if isinstance(user_input, dict) else str(user_input)
    if not user_text:
        speak("ごめんね、もう一度聞かせてくれる？")
        return

    print(f"ユーザーの応答: {user_text}")
    status = confirm_task_completion(user_input, title)
    is_completed = status == "Completed"
    record_task_completion(task_id, is_completed)

    # ✅ タスクの完了 or 未完了に応じた反応
    if is_completed:
        initial_reply = "やったね〜！ぼくうれしいよ。"
    else:
        initial_reply = "また今度頑張ろうね。"

    # 🔁 雑談開始：最初の応答に返す
    chat_history = [
        {"role": "system", "content": "あなたは優しくて、ちょっととぼけたウサギのキャラクターです。ユーザーと自然な会話をしてください。"},
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": initial_reply}
    ]

    speak(initial_reply)

    # その後 2 回までやりとり
    for i in range(2):
        user_input = recognize_speech(timeout_seconds=60)
        user_text = user_input.get("text", "").strip() if isinstance(user_input, dict) else str(user_input)
        if not user_text:
            speak("また話そうね。")
            break

        chat_history.append({"role": "user", "content": user_text})

        ai_response = chat_model.invoke(chat_history)
        reply = ai_response.content.strip()
        chat_history.append({"role": "assistant", "content": reply})
        print(f"[雑談返答{i+1}]: {reply}")
        speak(reply)


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




# def confirm_task_completion(input_text: str, task_title: str) -> bool:
#     """
#     FEW-SHOT プロンプトを用いて、ユーザーの発話がタスク完了を意味するか判定する関数。
#     出力は以下の形式の JSON 形式で返してください:
#     {"status": "<Completed | NotCompleted>"}
#     ainのFew-shot判定 ＋ 補助ルールベースマッチで柔軟性を高める。
#     """
#     # input_text = input_text.strip().lower()
#     input_text = input_text.get("text", "").strip().lower()

#     # prompt = f"""
#     few_shot_prompt = """
# あなたはタスク完了確認アシスタントです。
# 以下のユーザー発話が、タスク完了を意味するか判定し、JSON形式で回答してください。

# 出力形式:
# {{"status": "<Completed | NotCompleted>"}}

# === FEW-SHOT EXAMPLES ===

# [例1]
# ユーザー発話:「完了」、「やったよ」、「DONE」
# 出力: 
# {{"status": "Completed"}}

# [例2]
# ユーザー発話:「まだです」
# 出力: 
# {{"status": "NotCompleted"}}

# [例3]
# ユーザー発話:「終わりました！」
# 出力: 
# {{"status": "Completed"}}

# [例4]
# ユーザー発話:「ちょっと待ってください」
# 出力: 
# {{"status": "NotCompleted"}}

# [例5] ユーザー発話:「入りました」「磨いた」「食べた」
# 出力: {{"status": "Completed"}}

# === END OF EXAMPLES ===

# 以下のユーザー発話: "{input_text}"
# """
#     prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
#     final_prompt = prompt_template.format(input_text=input_text)
#     print("AIに入力された文章：", final_prompt)
#     response = chat_model.invoke(final_prompt)
#     cleaned_content = response.content.strip().strip("```").strip()
#     print("AIから出力された文章：", response.content)
#     print("AIから出力された文章を綺麗にしたもの：", cleaned_content)

#     try:
#         result = json.loads(cleaned_content)
#         status = result.get("status", "NotCompleted")
#         return status if status in ["Completed", "NotCompleted"] else "NotCompleted"
    
#         # print("statusの値:", result)
#         # # 期待するキーは "status" です
#         # intent = result.get("status", "NotCompleted")
#         # return intent == "Completed"
#     except json.JSONDecodeError:
#         print("AIの応答をJSONとして解析できませんでした:", cleaned_content)
#         return "NotCompleted"