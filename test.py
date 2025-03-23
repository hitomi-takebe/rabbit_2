# import time
# import json
# import urllib
# import logging
# import requests
# from collections import defaultdict

# # ログ設定
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s")

# # 設定
# endpoint = 'https://acp-api-async.amivoice.com/v1/recognitions'
# app_key = '7E1A30FA20F63BA05BB3CC46439CB1AA46C471A65C536625A0EC6426623DB31D84A004ED078FDF17A5'
# filename = 'amivoice-api-client-library-main/audio/test2.wav'
# FILE_NAME = "data.json"


# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s")

# # リクエストパラメータ
# domain = {
#     'grammarFileNames': '-a-general', #会話のジャンルによってエンジンを変更できます
#     'loggingOptOut': 'False',#ログ保存
#     'contentId': filename,#コンテンツID
#     'speakerDiarization': 'True',#話者ダイアライゼーション
#     'diarizationMinSpeaker': '2',#話者数指定
#     'diarizationMaxSpeaker': '2',
#     'sentimentAnalysis': 'True', #感情分析を有効にする
#     #'profileId': 'test',
#     'keepFillerToken': '1',#デフォルトは０になっている(フィラーが除去される)
# }
# params = {
#     'u': app_key,
#     'd': ' '.join([f'{key}={urllib.parse.quote(value)}' for key, value in domain.items()]),
# }
# logger.info(params)

# # ジョブのリクエストの送信
# request_response = requests.post(
#     url=endpoint,
#     data={key: value for key, value in params.items()},
#     files={'a': (filename, open(filename, 'rb').read(), 'application/octet-stream')}
# )

# if request_response.status_code != 200:
#     logger.error(f'Failed to request - {request_response.content}')
#     exit(1)

# request = request_response.json()

# if 'sessionid' not in request:
#     logger.error(f'Failed to create job - {request["message"]} ({request["code"]})')
#     exit(2)

# logger.info(request)

# # 結果が出るまで10秒ごとに状態を確認する
# while True:
#     # HTTP GETで`recognitions/{sessionid}`にリクエスト
#     result_response = requests.get(
#         url=f'{endpoint}/{request["sessionid"]}',
#         headers={'Authorization': f'Bearer {app_key}'}
#     )
#     if result_response.status_code == 200:
#         result = result_response.json()
#         if 'status' in result and (result['status'] == 'completed' or result['status'] == 'error'):
#             # レスポンスの`status`が`completed`か`error`になれば、結果を整形して出力
#             # 結果をファイルに保存
#             with open(FILE_NAME, 'w') as f:
#                 json.dump(result, f, ensure_ascii=False, indent=4)
#             # 終了
#             exit(0)
#         else:
#             # レスポンスの`status`が`completed`か`error`以外の場合は、ジョブの実行中
#             # なので、再度状態をチェックする前に少し待つ（ここでは10秒）
#             logger.info(result)
#             time.sleep(10)
#     else:
#         # HTTPのレスポンスコードが200以外の場合は終了する
#         logger.error(f'Failed. Response is {result_response.content} - {e}')
#         exit(3)

import time
import json
import urllib
import logging
import requests
from collections import defaultdict

# ログ設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s")

# 設定
endpoint = 'https://acp-api-async.amivoice.com/v1/recognitions'
app_key = '7E1A30FA20F63BA05BB3CC46439CB1AA46C471A65C536625A0EC6426623DB31D84A004ED078FDF17A5'
filename = 'amivoice-api-client-library-main/audio/test2.wav'
FILE_NAME = "data.json"

# リクエストパラメータ
domain = {
    'keepFillerToken' : '0',             # フィラーを除去
    'grammarFileNames': '-a-general',   # 会話のジャンルによってエンジンを変更できます
    'loggingOptOut': 'False',             # ログ保存
    'contentId': filename,                # コンテンツID
    'speakerDiarization': 'True',         # 話者ダイアライゼーション
    'diarizationMinSpeaker': '1',         # 話者数指定
    'diarizationMaxSpeaker': '2',
    'sentimentAnalysis': 'True',          # 感情分析を有効にする
    #'profileId': 'test',
    'keepFillerToken': '1',               # デフォルトは０になっている(フィラーが除去される)
}
params = {
    'u': app_key,
    'd': ' '.join([f'{key}={urllib.parse.quote(value)}' for key, value in domain.items()]),
}
logger.info(params)

# ジョブのリクエストの送信
request_response = requests.post(
    url=endpoint,
    data={key: value for key, value in params.items()},
    files={'a': (filename, open(filename, 'rb').read(), 'application/octet-stream')}     #音声ファイルを読み込む
)

if request_response.status_code != 200:
    logger.error(f'Failed to request - {request_response.content}')
    exit(1)

request_json = request_response.json()

if 'sessionid' not in request_json:
    logger.error(f'Failed to create job - {request_json.get("message", "No message")} ({request_json.get("code", "No code")})')
    exit(2)

logger.info(request_json)

# 結果が出るまで10秒ごとに状態を確認する
while True:
    # HTTP GETで`recognitions/{sessionid}`にリクエスト
    result_response = requests.get(
        url=f'{endpoint}/{request_json["sessionid"]}',
        headers={'Authorization': f'Bearer {app_key}'}
    )
    if result_response.status_code == 200:
        result = result_response.json()
        if 'status' in result and (result['status'] == 'completed' or result['status'] == 'error'):
            # 結果をファイルに保存
            with open(FILE_NAME, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4) #結果をファイルに保存
            logger.info("ジョブ完了。結果を data.json に保存しました。")

            # 感情分析の部分が存在する場合、平均点を計算する
            # ここでは、result内に "sentimentAnalysis" キーがあり、その中に各スコアが含まれている前提です。
            sentiment = result.get("sentimentAnalysis")  # 感情分析の結果
            if sentiment and isinstance(sentiment, dict):
                # "starttime" と "endtime" を除いた数値のスコアを抽出
                scores = [value for key, value in sentiment.items()
                          if key not in ("starttime", "endtime") and isinstance(value, (int, float))]
                if scores:
                    average_score = sum(scores) / len(scores)
                    logger.info(f"感情分析の平均点: {average_score:.2f}")
                else:
                    logger.info("感情分析のスコアが見つかりませんでした。")
            else:
                logger.info("感情分析情報が存在しません。")

            # さらに全文の text が存在すれば抽出してログ出力（オプション）
            full_text = result.get("text")
            if full_text:
                logger.info("認識結果全文:")
                logger.info(full_text)
            exit(0)
        else:
            # ジョブが実行中の場合は、結果をログに出力して10秒待つ
            logger.info(result)
            time.sleep(10)
    else:
        logger.error(f'Failed. Response is {result_response.content}')
        exit(3)
