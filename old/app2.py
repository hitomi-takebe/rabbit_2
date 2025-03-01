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

#音声入力
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
        q
#音声出力（gTTS + playsound）
def speak(text):
    tts = gTTS(text=text, lang="ja")
    tts.save("output.mp3")
    playsound.playsound("output.mp3")
    os.remove("output.mp3")

#タスクの登録
# def add_task(user_id, task, reminder_time=None):
# data = {"user_id": user_id, "task": task, "status": "未完了", "reminder_time": reminder_time}
# response = supabase.table("tasks").insert(data).execute()
# speak(f"タスク '{task}' を登録しました！")


def chat_with_ai(user_input):
    chat = ChatOpenAI(model_name="gpt-3.5-turbo")

    prompt = f"あなたは親しみやすいおせっかいなAIキャラクターです。適度にゆるい感じで、次の質問に答えてください: {user_input}"
    response = chat.predict(prompt)
    speak(response)

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