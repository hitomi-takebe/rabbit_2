# task_registration.py
import json
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from audio import speak, recognize_speech
from config import CURRENT_USER_ID, supabase
# 設定情報をconfig.pyからインポート
from config import chat_model, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase
#タスクの登録機能ができるようになっていないです


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

def classify_confirmation(response_text: str) -> str:
    """
    ユーザーの確認応答を解析し、「Yes」または「No」かを判定する関数。
    出力は必ず次の JSON 形式で返してください：
    {
      "confirmation": "<Yes | No>"
    }
    """
    prompt = """
あなたは、以下のユーザーの応答を解析し、それが確認の「イエス」か「ノー」かを判定してください。
出力は必ず次の JSON 形式で返してください：
{{"confirmation": "<Yes | No>"}}

=== FEW-SHOT EXAMPLES ===
User response: "はい"、 "イエス"、 "そう"、 "OK"、 "あってる"、 "そうそう"、 "承知しました"、 "うん"など
Output: {{"confirmation": "Yes"}}
User response: "いいえ"、 "ノー"、 "違う"、 "ちがう"、 "間違ってる"、 "やり直す" など
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
            # 全ての情報が取得できたらループを抜ける
        break   

    # 取得した情報を変数に格納
    title = task_info["title"]
    scheduled_time = task_info["scheduled_time"]
    

    # 最終確認：内容を「{scheduled_time} に {title} する」で確認
    while True:
        speak(f"確認します。毎日 {scheduled_time} に {title}  で登録して良いですか？「はい」か「いいえ」で答えてください。")
        confirmation_raw = recognize_speech(timeout_seconds=30)
        confirmation = classify_confirmation(confirmation_raw)
        if confirmation == "No":
            speak("了解しました。もう一度、最初からやり直します。")
            return insert_task()  # 再帰的に再入力
        elif confirmation == "Yes":
            break
        else:
            speak("確認が取れなかったので、もう一度お答えください。")

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
