import os
import json
import speech_recognition as sr
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

# OpenAI APIキーを直接設定
OPENAI_API_KEY = ""

# Supabase の設定
SUPABASE_URL = ""
SUPABASE_KEY = ""
CURRENT_USER_ID = ""  # 仮のユーザーID
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ChatOpenAI（LangChain）クライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

def recognize_speech(prompt):
    """音声入力を受け付け、認識結果の文字列を返す"""
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
        return recognize_speech(prompt)
    except sr.RequestError:
        print("音声認識サービスに接続できませんでした。")
        return None

def extract_task_info(input_text):
    """
    OpenAI（LangChain）を使い、入力文からタスク情報を抽出する。
    出力例：
    {
       "title": "お風呂に入る",
       "scheduled_time": "21:00:00"
    }
    """
    prompt = PromptTemplate(
        input_variables=["input_text"],
        template="""
        あなたはタスクの記述文から、タスクのタイトルと予定時刻（24時間表記のHH:MM:SS）を抽出するアシスタントです。
        以下の入力文から、タスクのタイトルと予定時刻を抽出し、以下の形式のJSONを出力してください。

        入力文: "{input_text}"

        出力形式（例）:
        {{
          "title": "お風呂に入る",
          "scheduled_time": "21:00:00"
        }}

        出力は必ず有効なJSON形式で返してください。
        """
    )
    formatted_prompt = prompt.format(input_text=input_text)

    # OpenAI APIを呼び出して応答を取得
    response = chat_model.invoke(formatted_prompt)

    try:
        # `response.content` は `AIMessage` のオブジェクトなので、直接 str に変換
        task_info = json.loads(response.content.strip("`"))  
        return task_info
    except json.JSONDecodeError as e:
        print("JSONの解析に失敗しました:", e)
        print("応答内容:", response.content)
        return None

def insert_task():
    """音声入力とOpenAIの抽出結果をもとに、Supabaseのtasksテーブルにタスクを登録する"""
    # 例: ユーザーにタスク全体の発言を促す
    input_text = recognize_speech("タスクを発言してください（例: 『毎日9時にお風呂に入る。』）")
    if not input_text:
        return

    # OpenAIに入力文からタスク情報を抽出させる
    task_info = extract_task_info(input_text)
    if not task_info:
        print("タスク情報の抽出に失敗しました。")
        return

    title = task_info.get("title")
    scheduled_time = task_info.get("scheduled_time")
    
    if not title or not scheduled_time:
        print("抽出結果に不足があります:", task_info)
        return

    # DBに登録するデータ
    task_data = {
        "user_id": CURRENT_USER_ID,
        "title": title,
        "recurrence": "everyday",
        "scheduled_time": scheduled_time  
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
