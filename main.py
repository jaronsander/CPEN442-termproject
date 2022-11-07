from passgate import PassgateAPI
from flask import Flask, request, abort
import os
from twilio.rest import Client
from dotenv import load_dotenv
from twilio.twiml.voice_response import Gather, VoiceResponse


ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
pAPI = PassgateAPI()

def authorize():
    auth = request.headers['Authorization']
    if auth is None:
        return False
    else:
        title,token = auth.split(" ")
        if title is None or title != "Bearer" or token is None:
            return False
        return pAPI.authorizeClient(token), token

@app.route("/requestcode", methods=['GET'])
def getcode():
    auth,client_api_token = authorize()
    if not auth:
        abort(403)
    uname = request.args['username']
    phone = request.args['phone']
    timeout = request.args['timeout']
    if uname is None or phone is None or timeout is None:
        abort(400)
    code = pAPI.setCode(client_api_token,uname,phone,timeout)
    if code is None:
        abort(400)
    return code

@app.route("/auth/<user_token>",methods=['GET'])
def authenticate(user_token):
    auth, client_api_token = authorize()
    if not auth:
        abort(403)
    ret = pAPI.makeCall(user_token)
    return {"authorized":ret}

@app.route("/twilio_answer/<twiliotoken>", methods=['POST'])
def twilio_answer(twiliotoken):
    pAPI.registerTwilioAnswer(twiliotoken,request.values['Digits'])

if __name__ == '__main__':
    context = ('ssl_certs/local_api_cert.crt', 'ssl_certs/local_api_key.key')
    app.run(ssl_context=context,threaded=True, port=5000)
