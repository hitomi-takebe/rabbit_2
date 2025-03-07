# task_registration.py
import json
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from audio import speak, recognize_speech
from config import CURRENT_USER_ID, supabase
# 設定情報をconfig.pyからインポート
from config import chat_model, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase




def extract_task_info(input_text: str) -> dict:
    """
    タスクの記述文から、タスクタイトルと予定時刻（HH:MM:SS）を抽出する。
    例:
    {
      "title": "お風呂に入る",
      "scheduled_time": "21:00:00"  // 時刻がなければ null
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

# def insert_task():
#     """
#     タスク登録機能:
#     ユーザーにタスク詳細を音声で尋ね、内容を抽出して DB に登録する。
#     """
#     speak("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")
#     text_for_task = recognize_speech(timeout_seconds=120)
#     if not text_for_task:
#         speak("うまく聞き取れませんでした。タスク登録を中断します。")
#         return
#     task_info = extract_task_info(text_for_task)
#     if not task_info or not task_info.get("title"):
#         speak("タスクのタイトルが取得できませんでした。登録を中止します。")
#         print("抽出結果:", task_info)
#         return
#     title = task_info["title"]
#     scheduled_time = task_info.get("scheduled_time", None)
#     data = {
#         "user_id": CURRENT_USER_ID,
#         "title": title,
#         "recurrence": "everyday",  # 毎日タスクの例
#         "scheduled_time": scheduled_time
#     }
#     try:
#         res = supabase.table("tasks").insert(data).execute()
#         if res.data:
#             print("タスクを登録しました:", res.data)
#             speak("タスクを登録しました。ありがとうございます。")
#         else:
#             print("タスク登録に失敗:", res)
#             speak("タスク登録に失敗しました。")
#     except Exception as e:
#         print("DB処理でエラー:", e)
#         speak("タスク登録の途中でエラーが発生しました。")

def insert_task():
    """
    タスク登録機能:
    ユーザーにタスク詳細を音声で尋ね、内容を抽出して DB に登録する。
    なお、抽出結果が不十分な場合は、個別に再入力させる。
    最終確認で「やり直し」と言われた場合も、再入力を促す。
    """
    speak("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")
    while True:
        # タスク詳細の入力
        text_for_task = recognize_speech(timeout_seconds=120)
        if not text_for_task:
            speak("うまく聞き取れませんでした。もう一度話してください。")
            continue

        # タスク情報の抽出
        task_info = extract_task_info(text_for_task)
        
        # 抽出結果そのものが取得できなかった場合
        if not task_info:
            speak("入力内容からタスク情報を抽出できませんでした。もう一度言ってください。")
            print("抽出結果:", task_info)
            continue
        
        # タスクのタイトルが取得できなかった場合
        if not task_info.get("title"):
            speak("タスクのタイトルが見つかりませんでした。タスクの内容をもう一度、はっきりと話してください。")
            print("抽出結果:", task_info)
            continue
        
        # タスクの実行時刻が取得できなかった場合
        if not task_info.get("scheduled_time"):
            speak("タスクの実行時刻が見つかりませんでした。必ず時刻を含めて、もう一度言ってください。")
            print("抽出結果:", task_info)
            continue

        # 取得した情報を変数に格納
        title = task_info["title"]
        scheduled_time = task_info["scheduled_time"]

        # 最終確認
        speak(f"確認します。毎日 {scheduled_time} に {title} する で登録して良いですか？　はい、または、いいえと答えてください。")
        confirmation = recognize_speech(timeout_seconds=30).lower()
        if "いいえ" in confirmation or "NO" in confirmation:
            speak("了解しました。もう一度、最初からやり直します。")
            continue  # ループの先頭に戻って再入力
        elif "はい" in confirmation or "Yes" in confirmation:
            break  # 最終確認OKならループを抜ける
        else:
            speak("確認できなかったので、もう一度入力してください。")
            continue

    # ループを抜けた時点で、title と scheduled_time は正しく取得されているはず
    data = {
        "user_id": CURRENT_USER_ID,
        "title": title,
        "recurrence": "everyday",  # 毎日タスクの例
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
        speak("タスク登録中にエラーが発生しました。")
