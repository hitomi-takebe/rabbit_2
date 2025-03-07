# task_registration.py
import json
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from audio import speak, recognize_speech
from config import CURRENT_USER_ID, supabase
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase

chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)



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

def insert_task():
    """
    タスク登録機能:
    ユーザーにタスク詳細を音声で尋ね、内容を抽出して DB に登録する。
    """
    speak("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")
    text_for_task = recognize_speech(timeout_seconds=120)
    if not text_for_task:
        speak("うまく聞き取れませんでした。タスク登録を中断します。")
        return
    task_info = extract_task_info(text_for_task)
    if not task_info or not task_info.get("title"):
        speak("タスクのタイトルが取得できませんでした。登録を中止します。")
        print("抽出結果:", task_info)
        return
    title = task_info["title"]
    scheduled_time = task_info.get("scheduled_time", None)
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
        speak("タスク登録の途中でエラーが発生しました。")
