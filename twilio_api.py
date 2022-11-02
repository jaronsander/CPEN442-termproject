import os
from twilio.rest import Client
from dotenv import load_dotenv
from twilio.twiml.voice_response import Gather, VoiceResponse

class Twilio_api():
    def __init__(self):
        load_dotenv()
        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        self.client = Client(account_sid, auth_token)
        self.response = self.create_resonse()

    def create_resonse(self):
        response = VoiceResponse()
        response.gather(num_digits=4, input='dtmf', timeout=5)
        return response


    def make_call(self, outgoing_num):
        call = self.client.calls.create(
            twiml=self.response,
            to=outgoing_num,
            from_='+16042452494'
        )
        return call