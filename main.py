from passgate import PassgateAPI
from flask import Flask, request, abort
import os

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
pAPI = PassgateAPI()


def authorize():
    auth = request.headers['Authorization']
    if auth is None:
        return False
    else:
        title, token = auth.split(" ")
        if title is None or title != "Bearer" or token is None:
            return False
        return pAPI.authorizeClient(token), token


@app.route("/requestcode", methods=['GET'])
def getcode():
    auth, client_api_token = authorize()
    if not auth:
        abort(403)
    phone = request.args['phone']
    timeout = request.args['to']
    if phone is None or timeout is None:
        abort(400)
    code = pAPI.setCode(client_api_token, phone, int(timeout))
    if code is None:
        abort(400)
    return code


@app.route('/requestsms', methods=['GET'])
def requestsms():
    auth, client_api_token = authorize()
    if not auth:
        abort(403)
    phone = request.args['phone']
    if phone is None:
        abort(400)
    # token = pAPI.reqSMS(client_api_token, phone)
    token = pAPI.reqRec(client_api_token, phone)
    if token is None:
        abort(400)
    return token


@app.route("/auth/<user_token>", methods=['GET'])
def authenticate(user_token):
    auth, client_api_token = authorize()
    if not auth:
        abort(403)
    ret = pAPI.makeCall(user_token)
    return {"authorized": ret}


@app.route("/auth/<user_token_SMS>/SMS", methods=['GET'])
def verify_SMS_code(user_token_SMS):
    auth, client_api_token = authorize()
    if not auth:
        abort(403)
    code = str(request.args.get('code'))
    ret = pAPI.verifySMS(user_token_SMS, code)
    return {"authorized": ret}


@app.route("/twilio_answer/<twiliotoken>", methods=['POST'])
def twilio_answer(twiliotoken):
    pAPI.registerTwilioAnswer(twiliotoken, request.values['Digits'])
    return ''


if __name__ == '__main__':
    context = ('ssl_certs/local_api_cert.crt', 'ssl_certs/local_api_key.key')
    app.run(threaded=True, port=5002)
