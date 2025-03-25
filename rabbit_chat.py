# # rabbit_chat.py
# from audio import speak, recognize_speech
# # 設定情報をconfig.pyからインポート
# from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


# # def rabbit_chat():
# #     """
# #     rabbit風雑談機能:
# #     ユーザーから雑談の発話があった場合に、簡単な応答を返す。
# #     """
# #     speak("会話モードです。何かお話ししますか？")
# #     user_input = recognize_speech(timeout_seconds=15)
# #     if user_input:
# #         speak("なるほど、勉強になります！")
# #     else:
# #         speak("何も聞こえませんでした。")
# #     # 関数が終了すると、自動的に呼び出し元に戻ります。
# #     return

# def rabbit_chat():
#     """
#     rabbit風雑談機能:
#     ユーザーから雑談の発話があった場合に、簡単な応答を返す。
#     """
#     speak("会話モードです。何かお話ししますか？")
#     user_input = recognize_speech(timeout_seconds=15)
#     if user_input:
#         speak("なるほど、勉強になります！")
#     else:
#         speak("何も聞こえませんでした。")
#     # 関数が終了すると、自動的に呼び出し元に戻ります。
#     return


from audio import recognize_speech, speak
from config import chat_model
from typing import List, Dict, Tuple
import time

# ChatGPTの初期設定（人格設定）
system_settings = """
あなたはとてもやさしく、話し相手として最高の友人です。相手の気持ちの前提は話さず、ユーザーのコメントの長さと同じ程度の文章量で話してください。少し踏み込んだ話をユーザーがしてきた場合でも、20秒程度の回答にしてください。
"""

# ChatGPTとの会話処理
def completion(new_message_text: str, past_messages: List[Dict]) -> Tuple[str, List[Dict]]:
    if len(past_messages) == 0 and len(system_settings) != 0:
        system = {"role": "system", "content": system_settings}
        past_messages.append(system)

    new_message = {"role": "user", "content": new_message_text}
    past_messages.append(new_message)

    result = chat_model.invoke(past_messages)  # LangChain経由で呼び出す
    response_message = {"role": "assistant", "content": result.content}
    past_messages.append(response_message)

    return result.content, past_messages

# 会話終了判定（ChatGPTに尋ねる）
def should_end_conversation(user_text: str) -> bool:
    check_messages = [
        {"role": "system", "content": "次のユーザーの発言が会話を終了したい意図があるかをYesかNoで答えてください。理由や説明はいりません。"},
        {"role": "user", "content": f"ユーザーの発言: {user_text}"}
    ]
    result = chat_model.invoke(check_messages)
    reply = result.content.strip().lower()
    return "yes" in reply

# メインループ
def rabbit_chat():
    messages: List[Dict[str, str]] = []

    while True:
        recog_result = recognize_speech()
        recog_text = recog_result["text"]
        ai_emotions = recog_result["ai_emotions"]

        if recog_text.strip() == "":
            speak("ごめんなさい、うまく聞き取れませんでした。もう一度お願いします。")
            continue

        print("ユーザー：", recog_text)

        if should_end_conversation(recog_text):
            speak("会話を終了します。また話しましょう。")
            time.sleep(1.5)  # ← これで確実に喋る時間を確保
            break

        # # 感情分析情報も含めて送信
        # if ai_emotions:
        #     recog_text += f"\n（感情分析の情報）\n{ai_emotions}"

        new_message, messages = completion(recog_text, messages)
        print("ChatGPT：", new_message)
        speak(new_message)
