"""
Google Calendar client - fetch calendar events
"""

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os
import pickle


class CalendarClient:
    """Client for Google Calendar API"""
    
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    
    def __init__(self, credentials_path="./credentials.json"):
        self.credentials_path = credentials_path
        self.service = self._build_service()
    
    def _build_service(self):
        """Build Google Calendar service"""
        try:
            creds = None
            
            # Load token if exists
            if os.path.exists("token.pickle"):
                with open("token.pickle", "rb") as token:
                    creds = pickle.load(token)
            
            # If no valid creds, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(GoogleRequest())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save for next time
                with open("token.pickle", "wb") as token:
                    pickle.dump(creds, token)
            
            return build("calendar", "v3", credentials=creds)
        except Exception as e:
            print(f"Calendar service build error: {e}")
            return None
    
    def get_upcoming_events(self, hours=2):
        """Get upcoming events in the next N hours"""
        if not self.service:
            return []
        
        try:
            now = datetime.utcnow().isoformat() + "Z"
            later = (datetime.utcnow() + timedelta(hours=hours)).isoformat() + "Z"
            
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=now,
                timeMax=later,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            events = events_result.get("items", [])
            
            return [
                {
                    "summary": e.get("summary", "Untitled"),
                    "start": e["start"].get("dateTime", e["start"].get("date")),
                    "end": e["end"].get("dateTime", e["end"].get("date"))
                }
                for e in events
            ]
        except Exception as e:
            print(f"Calendar events fetch error: {e}")
            return []
    
    def get_day_summary(self, date=None):
        """Get all events for a given day"""
        if not self.service or not date:
            return []
        
        try:
            start = datetime.fromisoformat(date).replace(hour=0, minute=0, second=0)
            end = start + timedelta(days=1)
            
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=start.isoformat() + "Z",
                timeMax=end.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            return events_result.get("items", [])
        except Exception as e:
            print(f"Calendar day summary error: {e}")
            return []
    
    def has_conflicts(self, start_time, end_time):
        """Check if there are events in a time window"""
        if not self.service:
            return False
        
        try:
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=start_time.isoformat() + "Z",
                timeMax=end_time.isoformat() + "Z",
                maxResults=1
            ).execute()
            
            return len(events_result.get("items", [])) > 0
        except Exception as e:
            print(f"Calendar conflict check error: {e}")
            return False
