import twilio_api
from flask import Flask, request
import os
from twilio.rest import Client
from dotenv import load_dotenv
from twilio.twiml.voice_response import Gather, VoiceResponse

load_dotenv()
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']

client = Client(account_sid, auth_token)
app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/call", methods=['GET', 'POST'])
def call():
    resp = VoiceResponse()
    # Start our <Gather> verb
    # Put hostname in front of gather
    gather = Gather(num_digits=1, action='/gather')
    gather.say('For sales, press 1. For support, press 2.')
    resp.append(gather)
    call = client.calls.create(
        twiml=resp,
        to='+15875906624',
        from_='+16042452494'
    )

    return str(call)


@app.route('/gather', methods=['GET', 'POST'])
def gather():
    """Processes results from the <Gather> prompt in /call"""
    # Start our TwiML response
    resp = VoiceResponse()

    # If Twilio's request to our app included already gathered digits,
    # process them
    if 'Digits' in request.values:
        # Get which digit the caller chose
        choice = request.values['Digits']

        # <Say> a different message depending on the caller's choice
        if choice == '1':
            resp.say('You selected sales. Good for you!')
            return str(resp)
        elif choice == '2':
            resp.say('You need support. We will help!')
            return str(resp)
        else:
            # If the caller didn't choose 1 or 2, apologize and ask them again
            resp.say("Sorry, I don't understand that choice.")

    # If the user didn't choose 1 or 2 (or anything), send them back to /voice
    resp.redirect('/gather')

    return str(resp)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    app.run()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
