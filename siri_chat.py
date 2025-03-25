# rabbit_chat.py
from audio import speak, recognize_speech
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


def rabbit_chat():
    """
    rabbit風雑談機能:
    ユーザーから雑談の発話があった場合に、簡単な応答を返す。
    """
    speak("rabbitモードです。何かお話ししますか？")
    user_input = recognize_speech(timeout_seconds=15)
    if user_input:
        speak("なるほど、勉強になります！")
    else:
        speak("何も聞こえませんでした。")
    # 関数が終了すると、自動的に呼び出し元に戻ります。
    return
