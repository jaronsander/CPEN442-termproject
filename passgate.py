import datetime
import os
import secrets
import threading

from twilio.rest import Client
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.twiml.voice_response import Gather, VoiceResponse


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

    def generateTwiml(self,ngrokPrefix, twilioToken, requestTimeout):
        resulting_to = requestTimeout-20
        twiml = "<Response>" \
                    "<Gather action=\""+ngrokPrefix + twilioToken+"\" method=\"POST\" input=\"dtmf\" timeout=\""+str(resulting_to)+"\">" \
                        "<Say>Please input the 2 digits that have appeared on your screen in the following "+ str(resulting_to-2) +"</Say>"\
                    "</Gather>" \
                "</Response>"
        return twiml


class PassgateAPI:
    def __init__(self):
        self.twilio = TwilioWrapper()
        self.clientsList = self.loadClientsFromDB()
        self.clientsUserMap = {}
        self.userTokensMap = {}
        self.MIN_TIMEOUT = 40
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.twilioTokensMap = {}

    # Returns a map of the form {<client_auth_token> : ClientName }
    def loadClientsFromDB(self):
        # Note: in real application, we'd get that from a DB
        return ["5iv3TYphzQu-ZEoWgpMaGp7RRHXeEWsQzc7A9h2RKL4"]

    def authorizeClient(self, token):
        if token in self.clientsList:
            # Can authorize sucessfully!
            # First, generate an entry for the client in the clients UserMap if it doesn't have one yet
            if token not in self.clientsUserMap.keys():
                self.clientsUserMap.update({token: {}})
            return True
        return False

    # Assuming Client has already been authenticated using `clientToken`
    # Generates code for this Client's user `u`
    # `p` is the Client's user phone number
    # `t` is the Client's requested timeout
    def setCode(self,clientToken,u,p,t):
        if u is None or p is None or t is None:
            return None
        actualTimeout = min(t,self.MIN_TIMEOUT)
        userResponseToken = secrets.token_urlsafe(32)
        generatedCode = secrets.randbelow(100)
        clientMap = self.clientsUserMap[clientToken]
        # Note, if assertion fails, somehow one has managed to call method before authorization --> kill backend, there's a fail in our logic
        assert clientMap is not None
        if u in clientMap.keys():
            # Auth request already in place, either wait for timeout, or remove it
            # TODO: Maybe change this depending on what we decide it to do
            return None
        clientMap[u] = (generatedCode, p,actualTimeout)
        # Update Maps
        self.clientsUserMap[clientToken] = clientMap
        self.userTokensMap[userResponseToken] = (u, clientToken)
        # Schedule the removal of the token
        deschedule_date = datetime.datetime.now() + datetime.timedelta(seconds=actualTimeout)
        self.scheduler.add_job(func=self.removeToken,trigger='date',run_date=deschedule_date,args=[self,userResponseToken])
        # Return appropriate json
        return {'code': generatedCode, 'timeout': actualTimeout, 'response_at': "auth/"+userResponseToken}

    def removeToken(self,token):
        assert token is not None
        (user,client) = self.userTokensMap[token]
        assert user is not None and client is not None
        del self.userTokensMap[token]
        clientMap = self.clientsUserMap[client]
        assert clientMap is not None
        assert clientMap[user] is not None
        del clientMap[user]

    def makeCall(self, userToken):
        assert userToken is not None
        (user, client) = self.userTokensMap[userToken]
        assert user is not None and client is not None
        clientMap = self.clientsUserMap[client]
        assert clientMap is not None
        userInfo = clientMap[user]
        assert userInfo is not None
        (generatedCode, p,actualTimeout) = userInfo
        twilioToken = secrets.token_urlsafe(32)
        evt = threading.Event()
        self.twilioTokensMap.update({twilioToken:(userToken, False, evt)})
        generatedTwiml = self.twilio.generateTwiml("",twilioToken,actualTimeout)
        self.twilio.make_call(generatedTwiml,p)
        evt.wait()
        # Upon returning, we know the call has been completed
        # Note that `removeToken` will be called shortly in the future (if Twilio's API isn't too slow) --> we must only
        # delete the entry in the `twilioToken` map
        (userToken,result,evt) = self.twilioTokensMap[twilioToken]
        assert userToken is not None and result is not None and evt is not None
        del self.twilioTokensMap[twilioToken]
        return result

    def registerTwilioAnswer(self,twilioToken,digits):
        assert twilioToken is not None
        (userToken, result, evt) = self.twilioTokensMap[twilioToken]
        assert userToken is not None and result is not None and evt is not None
        (user, client) = self.userTokensMap[userToken]
        assert user is not None and client is not None
        clientMap = self.clientsUserMap[client]
        assert clientMap is not None
        userInfo = clientMap[user]
        assert userInfo is not None
        (generatedCode, p, actualTimeout) = userInfo
        auth = int(generatedCode) == int(digits)
        self.twilioTokensMap[twilioToken] = (userToken,auth,evt)
        evt.set()



