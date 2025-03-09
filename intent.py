# intent.py
import json
from langchain.prompts import PromptTemplate
from config import chat_model

def extract_intent_info(input_text: str) -> str:
    """
    FEW-SHOTプロンプトを用いて、ユーザーの発話から意図を判定する関数。
    システムのフロー:
      - 発言がない場合 → notifications.py (Silent)
      - 「Hi Siri！タスクを登録する」と発言 → task_registration.py (TaskRegistration)
      - 「Hi Siri！」とだけ発言 → siri_chat.py (SiriChat)
    """
    few_shot_prompt = """
あなたは音声アシスタントです。起動直後のシステムは次のフローで動作します:

- ユーザーが何も発言しなかった場合は通知機能（notifications.py）を実行します。
- ユーザーが「Hi Siri！タスクを登録する」と発言した場合はタスク登録機能（task_registration.py）を実行します。
- ユーザーが「Hi Siri！」とだけ発言した場合は雑談機能（siri_chat.py）を実行します。

入力されたユーザー発話に基づき、以下の形式のJSONのみを出力してください:
{{"intent": "<Silent | TaskRegistration | SiriChat>"}}

=== FEW-SHOT EXAMPLES ===

[例1]
ユーザー: 「Hi Siri！ タスクを登録する」
出力:
{{
  "intent": "TaskRegistration"
}}

[例2]
ユーザー: 「Hi Siri！」
出力:
{{
  "intent": "SiriChat"
}}

[例3]
ユーザー: （発言なし）
出力:
{{
  "intent": "Silent"
}}

[例4]
ユーザー: 「あいうえお」
出力:
{{
  "intent": "Silent"
}}

[例5]
ユーザー: 「タスクを登録する」
出力:
{{
  "intent": "Silent"
}}

=== END OF EXAMPLES ===

以下のユーザー発話: 「{input_text}」
この発話の意図を判定し、**JSON形式** で答えてください。
"""
    prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
    final_prompt = prompt_template.format(input_text=input_text)
    print("AIに入力された文章：",final_prompt)
    response = chat_model.invoke(final_prompt)
    cleaned_content = response.content.strip().strip("```").strip()
    print("AIから出力された文章：", response.content)
    print("AIから出力された文章を綺麗にしたもの：",cleaned_content)

    try:
        result = json.loads(cleaned_content)
        print("intentの値:", result)
        intent = result.get("intent", "Silent")
        if intent in ["Silent", "TaskRegistration", "SiriChat"]:
            return intent
        return "Silent"
    except (json.JSONDecodeError, AttributeError):
        print("意図解析に失敗しました。レスポンス:", response.content)
        return "Silent"
