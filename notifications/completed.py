# notifications/completed.py

import datetime
from audio import speak
from config import CURRENT_USER_ID, supabase

def mark_task_completed(task_id: str):
    """
    タスク完了の報告を DB に登録する処理。
    """
    now_str = datetime.datetime.now().isoformat()
    data = {
        "task_id": task_id,
        "user_id": CURRENT_USER_ID,
        "completed_at": now_str
    }
    try:
        response = supabase.table("task_completions").insert(data).execute()
        if response.data:
            print(f"タスク({task_id})を完了登録しました: {response.data}")
            speak("タスクを完了登録しました。お疲れ様です。")
        else:
            print("タスク完了登録に失敗しました:", response)
            speak("タスク完了の登録に失敗しました。")
    except Exception as e:
        print("DB登録でエラーが発生しました:", str(e))
        speak("タスク完了の登録でエラーが発生しました。")
