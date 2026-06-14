"""
Notion client - fetch tasks and daily context
"""

import requests
import json


class NotionClient:
    """Client for Notion API"""
    
    def __init__(self, api_key, tasks_db_id, my_day_page_id):
        self.api_key = api_key
        self.tasks_db_id = tasks_db_id
        self.my_day_page_id = my_day_page_id
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28"
        }
    
    def get_today_tasks(self):
        """Get tasks from My Day page"""
        try:
            url = f"{self.base_url}/pages/{self.my_day_page_id}"
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"Notion My Day fetch error: {e}")
            return None
    
    def get_tasks_by_status(self, status="To Do"):
        """Get tasks filtered by status"""
        try:
            url = f"{self.base_url}/databases/{self.tasks_db_id}/query"
            
            payload = {
                "filter": {
                    "property": "Status",
                    "select": {
                        "equals": status
                    }
                }
            }
            
            resp = requests.post(url, headers=self.headers, json=payload)
            if resp.status_code == 200:
                return resp.json().get("results", [])
            return []
        except Exception as e:
            print(f"Notion tasks fetch error: {e}")
            return []
    
    def get_upcoming_deadlines(self):
        """Get tasks with upcoming due dates"""
        try:
            url = f"{self.base_url}/databases/{self.tasks_db_id}/query"
            
            payload = {
                "sorts": [
                    {
                        "property": "Due Date",
                        "direction": "ascending"
                    }
                ]
            }
            
            resp = requests.post(url, headers=self.headers, json=payload)
            if resp.status_code == 200:
                return resp.json().get("results", [])
            return []
        except Exception as e:
            print(f"Notion deadlines fetch error: {e}")
            return []
    
    def log_learning(self, insight):
        """Log a learning/insight to the daily log"""
        try:
            # Create a new page in the Tasks database with the insight
            url = f"{self.base_url}/pages"
            
            payload = {
                "parent": {
                    "database_id": self.tasks_db_id
                },
                "properties": {
                    "Title": {
                        "title": [
                            {
                                "text": {
                                    "content": f"Learning: {insight[:50]}"
                                }
                            }
                        ]
                    }
                }
            }
            
            resp = requests.post(url, headers=self.headers, json=payload)
            return resp.status_code == 200
        except Exception as e:
            print(f"Notion learning log error: {e}")
            return False
