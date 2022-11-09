import datetime
import os
import secrets
import threading

from twilio.rest import Client
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.twiml.voice_response import Gather, VoiceResponse

ngrok_address = "https://fea5-128-189-150-96.ngrok.io/"

class TwilioWrapper:
    def __init__(self):
        load_dotenv()
        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        self.client = Client(account_sid, auth_token)
        self.number_from = os.environ['TWILIO_NUMBER']

    def make_call(self, twiml, outgoing_num):
        call = self.client.calls.create(
            twiml=twiml,
            to=outgoing_num,
            from_=self.number_from
        )
        return call

    def generateTwiml(self,ngrokPrefix, twilioToken, requestTimeout,clientName):
        resulting_to = requestTimeout-20
        twiml = "<Response>" \
                    "<Gather action=\""+ngrokPrefix + "twilio_answer/" +twilioToken+"\" method=\"POST\" input=\"dtmf\" numDigits=\"2\" timeout=\""+str(resulting_to)+"\">" \
                        "<Say>Login request for "+clientName+"'s services.\nPlease input the 2 digits that have appeared on your screen in the following "+ str(resulting_to-2) +" seconds. </Say>"\
                    "</Gather>" \
                "</Response>"
        return twiml


class PassgateAPI:
    def __init__(self):
        self.twilio = TwilioWrapper()
        self.clientsMap = self.loadClientsFromDB()
        self.userTokensMap = {}   # userResponseToken -> (generatedCode,phone#,timeout,clientName)
        self.twilioTokensMap = {} # twilioTokem -> (generatedCode,authFlag,threading.Event)
        self.MIN_TIMEOUT = 40
        self.MAX_TIMEOUT = 60
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    # Returns a map of the form {<client_auth_token> : ClientName }
    def loadClientsFromDB(self):
        # Note: in real application, we'd get that from a DB
        return {"5iv3TYphzQu-ZEoWgpMaGp7RRHXeEWsQzc7A9h2RKL4":"CashBank"}

    def authorizeClient(self, token):
        return token in self.clientsMap.keys()

    # Assuming Client has already been authenticated using `clientToken`
    # Generates code for this Client's user `u`
    # `p` is the Client's user phone number
    # `t` is the Client's requested timeout
    def setCode(self,clientToken,u,p,t):
        assert clientToken is not None and u is not None and p is not None and t is not None
        actualTimeout = min(max(t,self.MIN_TIMEOUT),self.MAX_TIMEOUT)
        userResponseToken = secrets.token_urlsafe(32)
        while userResponseToken in self.userTokensMap.keys():
            userResponseToken = secrets.token_urlsafe(32)
        generatedCode = secrets.randbelow(100)
        clientName = self.clientsMap[clientToken]
        assert clientName is not None
        self.userTokensMap[userResponseToken] = (generatedCode,p,actualTimeout, clientName)
        # Schedule the removal of the token
        deschedule_date = datetime.datetime.now() + datetime.timedelta(seconds=actualTimeout)
        try:
            self.scheduler.add_job(func=self.removeUserTokenFromMap, trigger='date', run_date=deschedule_date, args=[self, userResponseToken])
        except Exception as e:
            return
        # Return appropriate json
        return {'code': generatedCode, 'timeout': actualTimeout, 'response_at': "auth/"+userResponseToken}

    def removeUserTokenFromMap(self, token):
        assert token is not None
        val = self.userTokensMap[token]
        # Note: race condition possible here, but will assume it doesn't happen
        if val is not None:
            del self.userTokensMap[token]

    def makeCall(self, userToken):
        assert userToken is not None
        val = self.userTokensMap[userToken]
        assert val is not None
        (code, phone, timeout, clientName) = val
        evt = threading.Event()
        # generate a token == unique url, for twilio to answer
        twilioToken = secrets.token_urlsafe(32)
        while twilioToken in self.twilioTokensMap.keys():
            twilioToken = secrets.token_urlsafe(32)
        self.twilioTokensMap.update({twilioToken:(code, False, evt)})
        # get the twiml
        generatedTwiml = self.twilio.generateTwiml(ngrok_address,twilioToken,timeout,clientName)
        # Before making the call, we can remove the userToken from the map - this blocks the Client (Bank, or anyone
        # else randomly trying to guess the URL token to generate a phone call) to make further phone call requests for
        # that token - they will have to generate a new one (although for the same user) if they want to retry the call
        self.removeUserTokenFromMap(userToken)
        # Finally make the call
        self.twilio.make_call(generatedTwiml,phone)
        # wait for the call to finish
        evt.wait()
        # The call has finished, we can proceed by deleting the Twilio token from the Map, and returning the result
        result = self.twilioTokensMap[twilioToken]
        assert result is not None
        (code, authFlag, evt) = result
        del self.twilioTokensMap[twilioToken]
        return authFlag

    def registerTwilioAnswer(self,twilioToken,digits):
        assert twilioToken is not None and digits is not None
        result = self.twilioTokensMap[twilioToken]
        assert result is not None
        (code, authFlag, evt) = result
        auth = (int(code) == int(digits))
        self.twilioTokensMap[twilioToken] = (code,auth,evt)
        evt.set() # This wakes up the `make_call` thread that was waiting.
        # TODO: we might want to pass around the timeout and wake it up as well in case Twilio doesn't respond



