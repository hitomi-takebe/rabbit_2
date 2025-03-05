import os
import json
import pyttsx3
import speech_recognition as sr
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID
from supabase import create_client, Client


# =========================
# 1. 設定
# =========================
# Supabaseクライアントの初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ChatOpenAIクライアントの初期化
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

# pyttsx3の音声エンジン初期化
engine = pyttsx3.init()


# =========================
# 2. 音声合成 (TTS) 関数
# =========================
def speak(text: str):
    """指定したテキストを音声で読み上げる"""
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()


# =========================
# 3. 音声入力関数
# =========================
def recognize_speech(prompt="どうぞお話しください。"):
    """
    マイクから音声を取得し、日本語で認識して文字列を返す。
    先に speak(prompt) でプロンプトを読み上げたあと、ユーザーの発話を録音する。
    """
    print(prompt)

    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        print(prompt, "(発話をどうぞ...)")
        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        print("認識結果:", text)
        return text
    except sr.UnknownValueError:
        print("音声を認識できませんでした。")
        return ""
    except sr.RequestError:
        print("音声認識サービスに接続できませんでした。")
        return ""


# =========================
# 4. FEW-SHOTで意図を判定 (TaskRegistration / Others)
# =========================
def extract_intent_info(input_text: str) -> str:
    """
    FEW-SHOTプロンプトを使い、入力文章が「タスク登録かどうか」を判定。
    - "TaskRegistration" or "Others" を返す。

    *Pythonのフォーマット文字列と衝突しないよう、JSONの { } は {{ }} でエスケープ。
    """
    few_shot_prompt = """
あなたはユーザーの文章を読み取り、その意図を判断するアシスタントです。
可能な意図は以下の2つのみです:
1. TaskRegistration: ユーザーがタスクを登録しようとしている
2. Others: タスク登録とは無関係な内容

出力は以下の形式のJSON:
{{
  "intent": "TaskRegistration"  // または "Others"
}}

=== FEW-SHOT EXAMPLES ===

[Example 1]
User: "タスクを登録したいんだけど"
Assistant:
{{
  "intent": "TaskRegistration"
}}

[Example 2]
User: "今日はいい天気ですね"
Assistant:
{{
  "intent": "Others"
}}

=== END OF EXAMPLES ===

以下の文章: 「{input_text}」
を判定し、必ず上記JSON形式のみで答えてください。
"""
    prompt_template = PromptTemplate(
        input_variables=["input_text"],
        template=few_shot_prompt
    )
    final_prompt = prompt_template.format(input_text=input_text)

    response = chat_model.invoke(final_prompt)

    # JSON解析
    try:
        result = json.loads(response.content.strip())
        intent = result.get("intent", "Others")
        if intent in ["TaskRegistration", "Others"]:
            return intent
        return "Others"
    except (json.JSONDecodeError, AttributeError):
        print("intent解析に失敗しました。レスポンス:", response.content)
        return "Others"

# =========================
# 5. タスク詳細を抜き出す関数
# =========================
def extract_task_info(input_text: str) -> dict:
    """
    タスクのタイトル + 予定時刻 を抽出
    出力例:
    {
      "title": "お風呂に入る",
      "scheduled_time": "21:00:00"  // または null
    }

    *ここでも { } を {{ }} にエスケープ
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


# =========================
# 6. タスク登録 (DB挿入) + 音声応答
# =========================
def insert_task():
    """ 
    タスク詳細を音声で取得 → OpenAIで解析 → DBにINSERT 
    """
    text_for_task = recognize_speech("タスクの詳細を話してください。（例:『17時15分にお風呂に入る』など）")
    if not text_for_task:
        speak("うまく聞き取れませんでした。タスク登録を中断します。")
        return

    # タスク情報抽出
    task_info = extract_task_info(text_for_task)
    if not task_info or not task_info.get("title"):
        speak("タスクのタイトルが取得できませんでした。登録を中止します。")
        print("抽出結果:", task_info)
        return

    title = task_info["title"]
    scheduled_time = task_info.get("scheduled_time", None)

    # DBへINSERT
    data = {
        "user_id": CURRENT_USER_ID,
        "title": title,
        "recurrence": "everyday",  # 毎日タスクという例
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


# =========================
# 6. 常時起動ループ (「タスクを登録する」と言うと反応)
# =========================
def always_on_loop():
    """
    - プログラムはループ内でずっとマイクを待ち受ける
    - "タスクを登録" と言うなどでタスク登録の意図と判定されたら insert_task() を呼び出す
    - "シャットダウン" があればプログラム終了する
    """
    print("起動しました。いつでも『タスクを登録したい』『タスクを登録する』などと言ってください。シャットダウンで完全終了します。")
    speak("起動しました。いつでも『タスクを登録したい』や『タスクを登録する』などと言ってください。シャットダウンで完全終了します。")

    while True:
        user_text = recognize_speech()  # プロンプトなしで待機
        if not user_text:
            continue  # 発話が認識できなかった場合はループの先頭に戻る

        # キーワードチェック（各キーワードに対してin user_textを適用）
        if ("シャットダウン" in user_text or 
            "さようなら" in user_text):
            speak("プログラムを終了します。")
            print("プログラムを終了します。")
            break

        # FEW-SHOTでIntent判定
        intent = extract_intent_info(user_text)
        print("推定Intent:", intent)

        if intent == "TaskRegistration":
            insert_task()
        else:
            speak("タスク登録以外の会話ですね。特に処理は行いません。")
            print("→ Others")


# =========================
# 7. メイン実行
# =========================
if __name__ == "__main__":
    always_on_loop()