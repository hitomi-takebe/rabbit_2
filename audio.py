# audio.py
import threading
import os
import sounddevice as sd
import tempfile
from gtts import gTTS
import speech_recognition as sr
import time
# from pyAudioAnalysis import audioTrainTest as aT

speech_lock = threading.Lock()
# 設定情報をconfig.pyからインポート
from config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, CURRENT_USER_ID, supabase


#########################################
# ① 音声認識・感情分析関連の関数
#########################################

def speak(text: str):
    """テキストをgTTSを用いて読み上げる関数"""
    with speech_lock:
        try:
            tts = gTTS(text=text, lang="ja")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_filename = fp.name
            tts.save(temp_filename)
            os.system("mpg123 -q " + temp_filename)
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

def analyze_sentiment(file_path: str) -> dict:
    """
    ダミーの感情分析結果を返す関数です。
    ※ 実際には、ここで音声ファイル(file_path)を対象にAPI呼び出し等を実施してください。
    """
    # 例として、1件のダミーセグメントを返す
    return {
        "segments": [
            {
                "starttime": 0,
                "endtime": 3000,
                "energy": 10,
                "stress": 20,
                "confidence": 30
            }
        ]
    }

def process_sentiment_and_save(file_path: str, recognized_text: str) -> None:
    """
    指定された音声ファイルに対して感情分析を行い、各指標の平均値を計算して
    認識結果の全文(recognized_text)とともにSupabaseのsentiment_averagesテーブルへ保存します。
    """
    sentiment_result = analyze_sentiment(file_path)
    segments = sentiment_result.get("segments", [])
    if not segments:
        print("感情分析のセグメントが見つかりませんでした。")
        return

    sums = {}
    counts = {}
    for seg in segments:
        for key, value in seg.items():
            if key in ("starttime", "endtime"):
                continue
            if isinstance(value, (int, float)):
                sums[key] = sums.get(key, 0) + value
                counts[key] = counts.get(key, 0) + 1
    averages = {key: sums[key] / counts[key] for key in sums}
    print("感情分析の平均値:", averages)

    data = {
        "user_id": CURRENT_USER_ID,
        "talk": recognized_text,
        # 必要に応じて平均値なども保存可能
        # "energy": averages.get("energy"),
        # "stress": averages.get("stress"),
        # "confidence": averages.get("confidence"),
    }
    emotions = supabase.table("sentiment_averages").insert(data).execute()
    print("Supabaseへの登録結果:", emotions)

def get_latest_sentiment_data(user_id: str) -> dict:
    """
    指定ユーザーの最新の感情分析レコードをSupabaseから取得する。
    """
    res = supabase.table("sentiment_averages") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
    data = res.data
    if data and len(data) > 0:
        return data[0]
    else:
        return {}

def generate_ai_emotions_from_record(record: dict) -> str:
    """
    Supabaseに保存された感情分析結果レコード(record)をもとに、
    簡単な解釈文を生成します。（例：エネルギー、ストレスの傾向など）
    ※ 必要に応じて内容をカスタマイズしてください。
    """
    # ダミーの結果を返す例
    return "エネルギーは平均的で、ストレスは低い状態です。"

def recognize_speech_from_file(file_path: str) -> str:
    """
    録音済みのWAVファイル(file_path)から音声認識を実施し、テキストを返す。
    """
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        return text
    except sr.UnknownValueError:
        print("音声を認識できませんでした。")
        return ""
    except sr.RequestError:
        print("音声認識サービスに接続できませんでした。")
        return ""

#########################################
# ② 感情分類関連の関数（pyAudioAnalysis利用）
#########################################

# モデル名とタイプ（ファイルの存在・パス、拡張子などを確認してください）
# MODEL_NAME = "mySVMModel"
# MODEL_TYPE = "svm"

def record_audio(filename, duration=3, sr=16000):
    """マイクから音声を録音し、WAVファイルとして保存する関数"""
    print("録音開始...")
    try:
        audio = sd.rec(int(duration * sr), samplerate=sr, channels=1)
        sd.wait()
        sf.write(filename, audio, sr)
        print("録音終了")
    except Exception as e:
        print("録音中にエラーが発生しました:", e)
        raise e

def classify_emotion(file_path: str) -> str:
    """
    pyAudioAnalysis の file_classification を用いて、ファイルの感情分類を実施する関数。
    分類結果（感情ラベル）を返します。
    """
    try:
        result, probability, class_names = aT.file_classification(file_path, MODEL_NAME, MODEL_TYPE)
    except Exception as e:
        print("分類中にエラーが発生しました:", e)
        return None

    if not isinstance(class_names, list):
        print("モデルが見つからないか、分類に失敗しました。")
        return None

    try:
        emotion_label = class_names[int(result)]
        return emotion_label
    except Exception as e:
        print("感情ラベルの取得に失敗しました:", e)
        return None

def get_voice_input(timeout=5):
    """
    マイクから音声入力を取得し、Googleの音声認識APIで日本語テキストに変換する関数
    ※ インターネット接続が必要です。
    """
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("ご返答をどうぞ（「はい」または「いいえ」）：")
        try:
            audio = recognizer.listen(source, timeout=timeout)
            text = recognizer.recognize_google(audio, language="ja-JP")
            print("認識結果:", text)
            return text.lower()
        except sr.WaitTimeoutError:
            print("音声入力のタイムアウトが発生しました。")
            return ""
        except sr.UnknownValueError:
            print("音声を認識できませんでした。")
            return ""
        except Exception as e:
            print("音声認識中にエラーが発生しました:", e)
            return ""

#########################################
# メイン処理（統合処理）
#########################################

if __name__ == "__main__":
    while True:
        audio_file = "temp_recording.wav"
        
        # ①・② 共通の録音処理（1回の録音を利用）
        try:
            record_audio(audio_file, duration=3)
        except Exception:
            print("録音処理でエラーが発生したため、このループはスキップします。")
            continue

        # ②：pyAudioAnalysis による感情分類
        # emotion_label = classify_emotion(audio_file)
        # if emotion_label is None:
        #     continue
        # print("推定された感情:", emotion_label)
        # # 感情に応じた応答（例）
        # if emotion_label == "anger":
        #     response_text = "怒っているね、どうしたの？落ち着いて話してみよう。"
        # elif emotion_label == "disgust":
        #     response_text = "嫌がっているね。"
        # elif emotion_label == "fear":
        #     response_text = "恐れているね。勇気出して。"
        # elif emotion_label == "happy":
        #     response_text = "嬉しそうだね！話を続けて。"
        # elif emotion_label == "sad":
        #     response_text = "悲しそう....。話を続けて。"
        # elif emotion_label == "surprise":
        #     response_text = "驚いたね！話を続けて。"
        # else:
        #     response_text = "未知の感情です。"
        # print(response_text)
        # speak(response_text)
        
        # ①：録音ファイルから音声認識を実施し、テキストを取得
        recognized_text = recognize_speech_from_file(audio_file)
        print("認識結果:", recognized_text)
        
        # ①：感情分析＆Supabase登録処理
        # process_sentiment_and_save(audio_file, recognized_text)
        
        # # 最新の感情分析レコードからAI解釈結果を取得
        # record_data = get_latest_sentiment_data(CURRENT_USER_ID)
        # if record_data:
        #     ai_emotions = generate_ai_emotions_from_record(record_data)
        #     print("感情分析の情報:", ai_emotions)
        #     speak("感情分析の結果は、" + ai_emotions)
        # else:
        #     print("感情分析レコードが取得できませんでした。")
        
        # ループ継続のため、ユーザーに「はい／いいえ」を音声入力で確認
        response = get_voice_input(timeout=5)
        if "はい" in response:
            print("もう一度試します。")
            speak("もう一度試します。")
        else:
            print("終了します。")
            speak("終了します。")
            break
        
        time.sleep(1)




#過去分
# グローバルTTSエンジン（メインスレッドで利用）
# engine = pyttsx3.init()
speech_lock = threading.Lock()

# def speak(text: str):
#     """スレッドセーフにテキストを読み上げる（TTS）"""
#     with speech_lock:
#         engine.say(text)
#         engine.runAndWait()

# def speak(text: str):
#     with speech_lock:
#         try:
#             # gTTSで音声生成（日本語）
#             tts = gTTS(text=text, lang="ja")
#             # 一時的なMP3ファイルを作成
#             with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
#                 temp_filename = fp.name
#             tts.save(temp_filename)
#             # mpg123で再生（-q は再生中のログを抑制）
#             os.system("mpg123 -q " + temp_filename)
#         finally:
#             # 一時ファイルの削除
#             if os.path.exists(temp_filename):
#                 os.remove(temp_filename)




# analyze_sentiment 関数を先に定義する
def analyze_sentiment(file_path: str) -> dict:
    """
    ダミーの感情分析結果を返す関数です。
    実際には、ここで音声ファイル (file_path) を分析するAPI等にリクエストし、結果を取得してください。
    以下はサンプルとして2件のセグメントを返す例です。
    """
    return {
        "segments": [
            # {
            #     "starttime": 1000,
            #     "endtime": 2000,
            #     "energy": 3,
            #     "content": 0,
            #     "upset": 0,
            #     "aggression": 0,
            #     "stress": 10,
            #     "uncertainty": 15,
            #     "excitement": 12,
            #     "concentration": 8,
            #     "emo_cog": 20,
            #     "hesitation": 5,
            #     "brain_power": 25,
            #     "embarrassment": 0,
            #     "intensive_thinking": 30,
            #     "imagination_activity": 7,
            #     "extreme_emotion": 0,
            #     "passionate": 0,
            #     "atmosphere": 0,
            #     "anticipation": 10,
            #     "dissatisfaction": 0,
            #     "confidence": 14
            # },
            # {
            #     "starttime": 2100,
            #     "endtime": 3000,
            #     "energy": 2,
            #     "content": 0,
            #     "upset": 0,
            #     "aggression": 0,
            #     "stress": 20,
            #     "uncertainty": 15,
            #     "excitement": 14,
            #     "concentration": 10,
            #     "emo_cog": 22,
            #     "hesitation": 6,
            #     "brain_power": 27,
            #     "embarrassment": 0,
            #     "intensive_thinking": 32,
            #     "imagination_activity": 5,
            #     "extreme_emotion": 1,
            #     "passionate": 0,
            #     "atmosphere": -1,
            #     "anticipation": 8,
            #     "dissatisfaction": 0,
            #     "confidence": 16
            # }
        ]
    }

#音声認識を保存する

def process_sentiment_and_save(file_path: str, recognized_text: str) -> None:
    """
    指定された音声ファイル（file_path）に対して感情分析を実施し、
    セグメントごとに各指標の平均値を計算した上で、認識結果の全文（recognized_text）とともに
    Supabase の sentiment_averages テーブルに保存します。
    """
    # ダミーの感情分析結果を取得
    sentiment_result = analyze_sentiment(file_path)
    segments = sentiment_result.get("segments", [])
    
    if not segments:
        print("感情分析のセグメントが見つかりませんでした。")
        return

    sums = {}
    counts = {}
    for seg in segments:
        for key, value in seg.items():
            if key in ("starttime", "endtime"):
                continue
            if isinstance(value, (int, float)):
                sums[key] = sums.get(key, 0) + value
                counts[key] = counts.get(key, 0) + 1

    averages = { key: sums[key] / counts[key] for key in sums }
    print("感情分析の平均値:", averages)

    # Supabase に挿入するデータを作成（talk カラムに認識結果全文を保存）
    data = {
        "user_id": CURRENT_USER_ID,
        "talk": recognized_text,
        # "energy": averages.get("energy"),
        # "content": averages.get("content"),
        # "upset": averages.get("upset"),
        # "aggression": averages.get("aggression"),
        # "stress": averages.get("stress"),
        # "uncertainty": averages.get("uncertainty"),
        # "excitement": averages.get("excitement"),
        # "concentration": averages.get("concentration"),
        # "emo_cog": averages.get("emo_cog"),
        # "hesitation": averages.get("hesitation"),
        # "brain_power": averages.get("brain_power"),
        # "embarrassment": averages.get("embarrassment"),
        # "intensive_thinking": averages.get("intensive_thinking"),
        # "imagination_activity": averages.get("imagination_activity"),
        # "extreme_emotion": averages.get("extreme_emotion"),
        # "passionate": averages.get("passionate"),
        # "atmosphere": averages.get("atmosphere"),
        # "anticipation": averages.get("anticipation"),
        # "dissatisfaction": averages.get("dissatisfaction"),
        # "confidence": averages.get("confidence")
    }
    
    emotions = supabase.table("sentiment_averages").insert(data).execute()
    print("Supabaseへの登録結果:", emotions)

def get_latest_sentiment_data(user_id: str) -> dict:
    """
    現在のユーザー(user_id)の最新の感情分析レコードを Supabase から取得する。
    """
    res = supabase.table("sentiment_averages") \
                    .select("*") \
                    .eq("user_id", user_id) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()
    data = res.data
    if data and len(data) > 0:
        return data[0]
    else:
        return {}

def generate_ai_emotions_from_record(record: dict) -> str:
    """
    Supabase に保存された感情分析結果レコード (record) をもとに、
    エネルギー、ストレス、感情/バランス/論理の数値と解釈、さらに
    全体のポジティブ・ネガティブ集計結果を含む文章を生成します。
    """
    # # 個別の数値を取得（存在しない場合は 0 とする）
    # energy = record.get("energy", 0)
    # stress = record.get("stress", 0)
    # content = record.get("content", 0)  # 感情/バランス/論理に対応
    # # ポジティブな指標：エネルギー、興奮、confidence、anticipation など
    # positive = (
    #     record.get("energy", 0) +
    #     record.get("excitement", 0) +
    #     record.get("confidence", 0) +
    #     record.get("anticipation", 0)
    # )
    # # ネガティブな指標：ストレス、upset、aggression、uncertainty、dissatisfaction など
    # negative = (
    #     record.get("stress", 0) +
    #     record.get("upset", 0) +
    #     record.get("aggression", 0) +
    #     record.get("uncertainty", 0) +
    #     record.get("dissatisfaction", 0)
    # )
    
    # # エネルギーの解釈（例）
    # if energy <= 10:
    #     energy_interp = "低領域で、気落ちや退屈、疲労を示唆しています。"
    # elif energy <= 20:
    #     energy_interp = "快適な会話が行えている状態です。"
    # elif energy <= 40:
    #     energy_interp = "会話が盛り上がっている可能性があります。"
    # else:
    #     energy_interp = "非常に高いエネルギー状態で、感情が昂っています。"
    
    # # ストレスの解釈
    # if stress < 30:
    #     stress_interp = "リラックスしている状態です。"
    # elif stress < 70:
    #     stress_interp = "ややストレスを感じているようです。"
    # else:
    #     stress_interp = "強いストレスが感じられます。"
    
    # # 感情/バランス/論理（content）の解釈（例）
    # if content < 100:
    #     content_interp = "感情のバランスが崩れている可能性があります。"
    # elif content < 300:
    #     content_interp = "安定した感情バランスが保たれています。"
    # else:
    #     content_interp = "非常に良好な感情バランスが認められます。"
    
    # 文章としてまとめる、今後ここに感情分析結果を挿入します。
    emotions = (
        " "
        # "ユーザーの音声の感情分析結果は以下の通りです。これらを元に【伝えたい内容】を適切な表現で応答して、ユーザーを励ましてください。"
        # "\n"
        # f"【エネルギー】: {energy} 点（範囲: 0～100）。{energy_interp}\n"
        # f"【ストレス】: {stress} 点（範囲: 0～100）。{stress_interp}\n"
        # f"【感情/バランス/論理】: {content} 点（範囲: 1～500）。{content_interp}\n"
        # f"【ポジティブ：ネガティブ】：{positive}:{negative}\n"
    )
    return emotions

# #google speech to textを利用したもの
def recognize_speech(timeout_seconds=120) -> str:
    """
    マイクから音声を取得し、日本語で認識して文字列を返す。
    timeout_seconds: 録音の上限秒数
    """
    print(f"音声入力を待機しています... 最大{timeout_seconds}秒")
    recognizer = sr.Recognizer()
    text = ""           # ここで初期化する
    ai_emotions = ""
    emotion_label = ""

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=timeout_seconds, phrase_time_limit=timeout_seconds)
        except sr.WaitTimeoutError:
            print("指定時間内に音声が入力されませんでした。")
            return {"text": text, "ai_emotions": ai_emotions,"emotion_label": None}
        
    # speech_recognitionのAudioDataオブジェクトからWAVデータを取得し、一時的なWAVファイルに保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
        temp_wav = fp.name
        fp.write(audio.get_wav_data())


    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        # import amivoice  # amivoiceライブラリのインポート
        # client = amivoice.AmiVoiceClient(api_key="YOUR_API_KEY")
        # 同期的に音声認識を実施（認識結果が返るまでブロックします）
        # text = client.recognize(temp_wav)
        print("認識結果:", text)

        # 感情分析の結果処理と Supabase 登録を実施
        process_sentiment_and_save(temp_wav, text)

        # ここに pyAudioAnalysisの感情分類を追加
        # emotion_label = classify_emotion(temp_wav)
        # if emotion_label:
        #     print("推定された感情:", emotion_label)
        # else:
        #     print("感情分類に失敗しました。")

        # Supabaseに音声認識結果と感情分析結果を登録
        process_sentiment_and_save(temp_wav, text)


        # 最新の感情分析レコードを取得
        record = get_latest_sentiment_data(CURRENT_USER_ID)
        if record:
            ai_emotions = generate_ai_emotions_from_record(record)
            print("感情分析の情報:", ai_emotions)
        else:
            print("感情分析レコードが取得できませんでした。")
        # return {"text": text, "ai_emotions": ai_emotions},audio
                # 結果を辞書で返す（感情ラベルを含む）
        return {
            "text": text,
            "ai_emotions": ai_emotions,
            "emotion_label": emotion_label
        }


    except sr.UnknownValueError:
        print("音声を認識できませんでした。")
        return {"text": text, "ai_emotions": ai_emotions, "emotion_label": None}
    except sr.RequestError:
        print("音声認識サービスに接続できませんでした。")
        return {"text": text, "ai_emotions": ai_emotions, "emotion_label": None}
    finally:
        # 作成した一時ファイルを削除
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

