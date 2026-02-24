import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def test_whatsapp():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_WHATSAPP_FROM')
    to_number = os.getenv('MY_WHATSAPP_NUMBER')
    
    print(f"Using Account SID: {account_sid}")
    print(f"From: {from_number}")
    print(f"To: {to_number}")
    
    client = Client(account_sid, auth_token)
    
    try:
        message = client.messages.create(
            body="Hello! This is a test message from your AI Meeting Scheduler to verify Twilio is working correctly. 🚀",
            from_=from_number,
            to=to_number
        )
        print(f"Success! Message SID: {message.sid}")
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")

if __name__ == "__main__":
    test_whatsapp()
