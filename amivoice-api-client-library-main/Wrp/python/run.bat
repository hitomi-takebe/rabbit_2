@set /P AppKey="7E1A30FA20F63BA05BB3CC46439CB1AA46C471A65C536625A0EC6426623DB31D84A004ED078FDF17A5"
set PYTHONPATH=src
set SSL_CERT_FILE=../../curl-ca-bundle.crt
python WrpSimpleTester.py wss://acp-api.amivoice.com/v1/ ../../audio/test.wav 16K -a-general %AppKey%
@pause