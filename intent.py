# intent.py
import json
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase

# ChatOpenAIクライアントの初期化（共通で利用）
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)

def extract_intent_info(input_text: str) -> str:
    """
    FEW-SHOTプロンプトを用いて、ユーザーの発話から意図を判定する。
    出力は "TaskRegistration" または "SiriChat" のどちらかとする。
    """
    few_shot_prompt = """
あなたは音声アシスタントです。ユーザーの発話を聞き、その意図を以下の2つのカテゴリに分類してください。

1. TaskRegistration: ユーザーがタスクを登録したい場合（例：「タスクを登録したい」）
2. SiriChat: ユーザーが雑談をしたい場合（例：「Hi Siri」）

出力は次の JSON 形式でお願いします：
{{
  "intent": "<TaskRegistration | SiriChat>"
}}

以下の発話：「{input_text}」
"""
    prompt_template = PromptTemplate(input_variables=["input_text"], template=few_shot_prompt)
    final_prompt = prompt_template.format(input_text=input_text)
    response = chat_model.invoke(final_prompt)
    try:
        result = json.loads(response.content.strip())
        intent = result.get("intent", "SiriChat")
        return intent if intent in ["TaskRegistration", "SiriChat"] else "SiriChat"
    except (json.JSONDecodeError, AttributeError):
        print("intent解析に失敗しました。レスポンス:", response.content)
        return "SiriChat"
