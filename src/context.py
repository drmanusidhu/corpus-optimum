"""
context.py — Pull today's calendar events and open Notion tasks.
Gives the agent awareness of your actual day before it messages you.
"""
import os
import json
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo

# ── Google Calendar ────────────────────────────────────────────────────────────
def fetch_calendar_events(days_ahead: int = 1) -> list[dict]:
    """Return today's (and optionally tomorrow's) calendar events."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle, pathlib

        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        token_path = pathlib.Path("./token.pickle")
        creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")

        creds = None
        if token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)

        service = build("calendar", "v3", credentials=creds)
        tz = ZoneInfo("Europe/London")
        now = datetime.now(tz)
        start = datetime(now.year, now.month, now.day, tzinfo=tz)
        end = start + timedelta(days=days_ahead)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for e in events_result.get("items", []):
            s = e.get("start", {})
            en = e.get("end", {})
            events.append({
                "title": e.get("summary", "Untitled"),
                "start": s.get("dateTime", s.get("date", "")),
                "end": en.get("dateTime", en.get("date", "")),
                "all_day": "date" in s and "dateTime" not in s,
                "description": e.get("description", ""),
            })
        return events

    except Exception as exc:
        return [{"error": str(exc)}]


# ── Notion Tasks ───────────────────────────────────────────────────────────────
def fetch_notion_tasks() -> list[dict]:
    """Return open tasks from the Notion tasks database."""
    try:
        from notion_client import Client

        notion = Client(auth=os.environ["NOTION_API_KEY"])
        db_id = os.environ["NOTION_TASKS_DB_ID"]

        today_str = date.today().isoformat()

        # Query for tasks that are not done and due today or overdue or have no date
        response = notion.databases.query(
            database_id=db_id,
            filter={
                "and": [
                    {
                        "property": "Status",
                        "status": {
                            "does_not_equal": "Done"
                        }
                    }
                ]
            },
            sorts=[
                {"property": "Due Date", "direction": "ascending"}
            ],
            page_size=30,
        )

        tasks = []
        for page in response.get("results", []):
            props = page.get("properties", {})

            # Extract title
            title_prop = props.get("Task name") or props.get("Name") or props.get("Title") or {}
            title_items = title_prop.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_items)

            # Extract status
            status_prop = props.get("Status", {})
            status = (status_prop.get("status") or {}).get("name", "")

            # Extract due date
            due_prop = props.get("Due Date") or props.get("Due") or {}
            due_date_obj = due_prop.get("date") or {}
            due_date = due_date_obj.get("start", "")

            # Extract priority
            priority_prop = props.get("Priority", {})
            priority_select = priority_prop.get("select") or {}
            priority = priority_select.get("name", "")

            if title:
                tasks.append({
                    "title": title,
                    "status": status,
                    "due_date": due_date,
                    "priority": priority,
                })

        return tasks

    except Exception as exc:
        return [{"error": str(exc)}]


def build_day_context() -> dict:
    """Combine calendar + tasks into a single context dict for the agent."""
    return {
        "date": date.today().isoformat(),
        "calendar_events": fetch_calendar_events(days_ahead=1),
        "notion_tasks": fetch_notion_tasks(),
    }
