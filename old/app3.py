import sqlite3
import os
import speech_recognition as sr
from gtts import gTTS
import playsound
from langchain_openai import ChatOpenAI  # 修正: langchain-openai を使用
from langchain.prompts import PromptTemplate
from supabase import create_client, Client
from dotenv import load_dotenv  # 環境変数の読み込み用

# .env ファイルを読み込む
load_dotenv()

print("✅ すべてのライブラリが正常にインポートされました！")

# OpenAI APIキーを設定
os.environ["OPENAI_API_KEY"] = "s"


# OpenAI APIキーを設定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ OpenAI APIキーが見つかりません。環境変数を設定してください。")

# Supabase の API キーと URL
SUPABASE_URL = ""
SUPABASE_KEY = ""

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Supabase の URL または APIキーが見つかりません。環境変数を設定してください。")

# Supabase クライアントを作成
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Supabase に接続しました！")

# 音声入力
def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 話してください...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio, language="ja-JP")
            print(f"📝 認識結果: {text}")
            return text
        except sr.UnknownValueError:
            print("⚠️ 音声を認識できませんでした。")
            return None
        except sr.RequestError:
            print("⚠️ 音声認識サービスに接続できません。")
            return None

# 音声出力（gTTS + playsound）
def speak(text):
    tts = gTTS(text=text, lang="ja")
    tts.save("output.mp3")
    playsound.playsound("output.mp3", block=True)  # 修正: block=True で同期再生
    os.remove("output.mp3")

# タスクの登録
def add_task(user_id, task, reminder_time=None):
    data = {"user_id": user_id, "task": task, "status": "未完了", "reminder_time": reminder_time}
    response = supabase.table("tasks").insert(data).execute()
    speak(f"タスク '{task}' を登録しました！")

# タスクの進捗を確認
def check_task_status():
    user_id = input("ユーザーIDを入力してください: ")
    response = supabase.table("tasks").select("*").eq("user_id", user_id).execute()
    
    tasks = response.data if response.data else []
    
    if not tasks:
        speak("現在のタスクはありません。")
    else:
        speak("あなたのタスク一覧です。")
        for task in tasks:
            speak(f"{task['task']} - {task['status']}")

# AIと会話
def chat_with_ai(user_input):
    chat = ChatOpenAI(model="gpt-3.5-turbo")  # 修正: 最新の `model` パラメータを使用
    prompt = f"あなたは親しみやすいおせっかいなAIキャラクターです。適度にゆるい感じで、次の質問に答えてください: {user_input}"
    
    response = chat.invoke(prompt)  # 修正: `predict()` ではなく `invoke()` を使用
    speak(response.content)  # 修正: `response` の `.content` を読み込む

if __name__ == "__main__":
    speak("こんにちは！おせっかいアシスタントです。何か手伝いましょうか？")

while True:
    print("\n=== 音声タスク管理アプリ ===")
    print("1. タスクを追加")
    print("2. タスクの進捗を確認")
    print("3. 雑談する")
    print("4. 終了")

    choice = input("選択肢を入力してください: ")

    if choice == "1":
        user_id = input("ユーザーIDを入力してください: ")
        speak("どんなタスクを追加しますか？")
        task = recognize_speech()
        if task:
            add_task(user_id, task)

    elif choice == "2":
        check_task_status()

    elif choice == "3":
        speak("何か話しかけてください。")
        user_input = recognize_speech()
        if user_input:
            chat_with_ai(user_input)

    elif choice == "4":
        speak("またね！")
        break

    else:
        speak("よく分かりません。もう一度選んでください。")
