# test_confirm.py
from notifications import confirm_task_completion

if __name__ == "__main__":
    input_text = [
        "完了しました",
    ]

    for phrase in input_text:
        result = confirm_task_completion(phrase)
        print(f"入力: '{phrase}' → 結果: {result}")

