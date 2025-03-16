# notifications/incomplete.py

from audio import speak

def handle_incomplete_task(task_id: str):
    """
    タスクが完了していなかった場合の処理。
    例として、ユーザーにその旨を伝え、後ほど再通知する（必要に応じて再通知処理を追加）。
    """
    print(f"タスク({task_id})は完了していませんでした。")
    speak("タスクが完了していないようです。後ほど再通知します。")
