import requests
import json

def verify():
    payload = {
        'user_id': 'final_verification_user',
        'request_text': 'schedule a 30m standup for tomorrow morning, title it allright meeting',
        'participants': ['mmjagtap007@gmail.com', '+919019758571']
    }
    
    print("Calling API on port 8002...")
    r = requests.post('http://127.0.0.1:8002/api/schedule', json=payload)
    data = r.json()
    
    print(f"Status: {r.status_code}")
    print(f"Success: {data.get('success')}")
    print(f"Message: {data.get('message')}")
    
    meeting = data.get('meeting')
    if meeting:
        print(f"Calendar Summary: {meeting.get('summary')}")
        print(f"Calendar Link: {meeting.get('calendar_link')}")
        print(f"Participants: {meeting.get('participants')}")
    
    print(f"Suggested Slots: {len(data.get('suggested_slots', []))}")

if __name__ == "__main__":
    verify()
