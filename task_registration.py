import json
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from audio import speak, recognize_speech
from config import CURRENT_USER_ID, supabase
from config import chat_model, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


def detect_cancel_intent(input_text: str) -> bool:
    """
    ユーザーの発話に「キャンセル」「やめる」などの中断意図が含まれていればTrueを返す
    """
    cancel_keywords = ["やめる", "キャンセル", "登録しない", "終了", "ストップ", "中止", "またあとで"]
    return any(kw in input_text for kw in cancel_keywords)


def extract_task_info(input_text: str) -> dict:
    if detect_cancel_intent(input_text):
        return {
            "title": None,
            "scheduled_time": None,
            "intent": "cancel"
        }

    prompt = PromptTemplate(
        input_variables=["input_text"],
        template="""
あなたは、ユーザーの発話から「タスク登録の意図があるか」「キャンセルの意図があるか」を判定し、
意図(intent)・タスクタイトル(title)・実行時刻(scheduled_time) を抽出してください。

出力は以下のJSON形式にしてください：

{{
  "title": "<タスク名 または null>",
  "scheduled_time": "<HH:MM:SS または null>",
  "intent": "<register または cancel>"
}}

入力: 「{input_text}」
"""
    )

    final_prompt = prompt.format(input_text=input_text)
    response = chat_model.invoke(final_prompt)

    try:
        task_info = json.loads(response.content.strip("`"))
        if task_info.get("intent") == "cancel":
            task_info["title"] = None
            task_info["scheduled_time"] = None
        return task_info
    except (json.JSONDecodeError, AttributeError) as e:
        print("タスク情報のJSON解析に失敗:", e)
        print("レスポンス:", response.content)
        return {}


def classify_confirmation(response_text: str) -> str:
    """
    ユーザーの確認応答を解析し、「Yes」または「No」かを判定する関数。
    出力は必ず次の JSON 形式で返してください：
    {
    "confirmation": "<Yes | No>"
    }
    """
    if detect_cancel_intent(response_text):
        return "No"

    prompt = """
あなたは、以下のユーザーの応答を解析し、それが確認の「イエス」か「ノー」かを判定してください。
出力は必ず次の JSON 形式で返してください：
{{"confirmation": "<Yes | No>"}}

=== FEW-SHOT EXAMPLES ===
User response: "そうです"、 "はい"、 "イエス"、 "そう"、 "OK"、 "あってる"、 "そうそう"、 "承知しました"、 "うん"など
Output: {{"confirmation": "Yes"}}
User response:  "やり直す" 、"いいえ"、 "ノー"、 "違う"、 "ちがう"、 "間違ってる"など
Output: {{"confirmation": "No"}}
=== END OF EXAMPLES ===

ユーザー応答: "{response_text}"
"""
    prompt_template = PromptTemplate(input_variables=["response_text"], template=prompt)
    final_prompt = prompt_template.format(response_text=response_text)
    openai_response = chat_model.invoke(final_prompt)
    print("確認応答解析結果:", openai_response.content)
    try:
        result = json.loads(openai_response.content.strip())
        confirmation = result.get("confirmation", "No")
        if confirmation not in ["Yes", "No"]:
            confirmation = "No"
        return confirmation
    except Exception as e:
        print("確認応答の解析エラー:", e)
        return "No"


def insert_task():
    """
    タスク登録機能:
    ユーザーにタスク詳細を音声で尋ね、内容を抽出して DB に登録する。
    なお、抽出結果が不十分な場合は、個別に再入力させる。
    最終確認で「やり直し」や「キャンセル」と言われた場合は再入力や中断。
    """
    speak("タスクの時間と内容を話してね。")
    while True:
        text_for_task = recognize_speech(timeout_seconds=120)
        if not text_for_task:
            speak("うまく聞き取れなかったよ。もう一度話してね。")
            continue

        if detect_cancel_intent(text_for_task):
            speak("わかったよ。タスクの登録をやめるね。")
            return

        task_info = extract_task_info(text_for_task)

        # intentがキャンセルなら終了
        if task_info.get("intent") == "cancel":
            speak("了解だよ。タスク登録はやめておくね。")
            return

        if not task_info:
            speak("入力内容からタスク情報を抽出できなかったよ。もう一度話してね。")
            continue

        if not task_info.get("title"):
            speak("タスクのタイトルが見つからなかったよ。もう一度話してね。")
            continue

        if not task_info.get("scheduled_time"):
            speak("タスクの実行時刻が見つからなかったよ。時刻を含めて、もう一度話してね。")
            continue

        break

    title = task_info["title"]
    scheduled_time = task_info["scheduled_time"]

    while True:
        speak(f"確認するね。毎日 {scheduled_time} に {title} で登録しても良いかな。「そうです」または「やり直す」、「キャンセル」で答えてね。")
        confirmation_raw = recognize_speech(timeout_seconds=30)

        if detect_cancel_intent(confirmation_raw):
            speak("了解だよ。タスクの登録をやめておくね。")
            return

        confirmation = classify_confirmation(confirmation_raw)
        if confirmation == "No":
            speak("了解！もう一度、最初からやり直すね。")
            return insert_task()
        elif confirmation == "Yes":
            break
        else:
            speak("確認が取れなかったから、もう一度答えてね。")

    data = {
        "user_id": CURRENT_USER_ID,
        "title": title,
        "recurrence": "everyday",
        "scheduled_time": scheduled_time
    }
    try:
        res = supabase.table("tasks").insert(data).execute()
        if res.data:
            print("タスクを登録しました:", res.data)
            speak("タスクを登録したよ。応援してるね。")
        else:
            print("タスク登録に失敗:", res)
            speak("タスク登録に失敗したみたい。")
    except Exception as e:
        print("DB処理でエラー:", e)
        speak("タスク登録中にエラーが発生しちゃった。")
