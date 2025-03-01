import sqlite3
import os
import speech_recognition as sr
from gtts import gTTS
import playsound
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from supabase import create_client, Client
import os

print("✅ すべてのライブラリが正常にインポートされました！")

# OpenAI APIキーを設定
os.environ["OPENAI_API_KEY"] = ""

# Supabase の API キーと URL（Supabaseの「Settings > API」から取得）
SUPABASE_URL = ""
SUPABASE_KEY = ""

# Supabase クライアントを作成
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("✅ Supabase に接続しました！")

#1データベースにタスクを追加する関数
def add_task(task, priority="未設定"):
    data = {"task": task, "priority": priority}
    response = supabase.table("tasks").insert(data).execute()
    print("✅ タスクが追加されました:", response)

#2タスク一覧を取得
def list_tasks():
    response = supabase.table("tasks").select("*").execute()
    tasks = response.data

    if not tasks:
        print("✅ タスクはありません。")
        return

    print("\n📋 タスク一覧：")
    for task in tasks:
        print(f"🆔 {task['id']} | {task['task']} | 優先度: {task['priority']}")

#3タスクを削除
def delete_task(task_id):
    response = supabase.table("tasks").delete().eq("id", task_id).execute()
    print("🗑️ タスクが削除されました！", response)

#4 AI を使ってタスクの優先度を決定


# OpenAI APIキー
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"

def prioritize_tasks():
    response = supabase.table("tasks").select("id, task").eq("priority", "未設定").execute()
    tasks = response.data

    if not tasks:
        print("🎉 すべてのタスクに優先度が設定されています！")
        return

    # AI モデル（GPT-3.5/4）
    chat = ChatOpenAI(model_name="gpt-3.5-turbo")

    # プロンプトテンプレート
    prompt_template = PromptTemplate(
        input_variables=["tasks"],
        template="以下のタスクの優先度を 高・中・低 で分類してください:\n\n{tasks}\n\n出力例:\n1. 高\n2. 中\n3. 低"
    )

    task_texts = "\n".join([f"{task['id']}. {task['task']}" for task in tasks])
    prompt = prompt_template.format(tasks=task_texts)

    response = chat.predict(prompt)
    priority_list = response.split("\n")

    for i, priority in enumerate(priority_list):
        task_id = tasks[i]['id']
        priority_label = priority.split(". ")[1] if ". " in priority else "未設定"
        supabase.table("tasks").update({"priority": priority_label}).eq("id", task_id).execute()

    print("✅ タスクの優先度を AI が設定しました！")

#5.修正後のタスク管理アプリの実行
if __name__ == "__main__":
    while True:
        print("\n=== Supabase タスク管理アプリ ===")
        print("1. タスクを追加")
        print("2. タスクを表示")
        print("3. タスクを削除")
        print("4. タスクを更新")
        print("5. AI で優先度を決定")
        print("6. 終了")

        choice = input("選択肢を入力してください: ")

        if choice == "1":
            user_id = input("ユーザーIDを入力してください: ")
            task = input("タスクを入力してください: ")
            start_time = input("開始時間を入力してください (YYYY-MM-DD HH:MM:SS): ") or None
            executed_id = input("実施者IDを入力してください (任意): ") or None
            add_task(user_id, task, start_time, executed_id)

        elif choice == "2":
            list_tasks()

        elif choice == "3":
            task_id = input("削除するタスクの ID を入力してください: ")
            delete_task(task_id)

        elif choice == "4":
            task_id = input("更新するタスクの ID を入力してください: ")
            new_task = input("新しいタスク内容（変更しない場合は空欄）: ") or None
            new_priority = input("新しい優先度（高・中・低、変更しない場合は空欄）: ") or None
            new_start_time = input("新しい開始時間 (YYYY-MM-DD HH:MM:SS、変更しない場合は空欄): ") or None
            new_executed_id = input("新しい実施者ID（変更しない場合は空欄）: ") or None
            update_task(task_id, new_task, new_priority, new_start_time, new_executed_id)

        elif choice == "5":
            prioritize_tasks()

        elif choice == "6":
            print("👋 アプリを終了します。")
            break

        else:
            print("⚠️ 無効な選択です。")
