"""
Oura API client - fetch ring data
"""

import requests
from datetime import datetime, timedelta


class OuraClient:
    """Client for Oura ring API v2"""
    
    def __init__(self, personal_access_token):
        self.token = personal_access_token
        self.base_url = "https://api.ouraring.com/v2/usercollection"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def get_latest_readiness(self):
        """Get today's readiness score"""
        try:
            url = f"{self.base_url}/daily_readiness"
            resp = requests.get(url, headers=self.headers, params={"limit": 1})
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return data[0] if data else {"score": 0}
            return {"score": 0}
        except Exception as e:
            print(f"Oura readiness fetch error: {e}")
            return {"score": 0}
    
    def get_latest_sleep(self):
        """Get last night's sleep data"""
        try:
            url = f"{self.base_url}/daily_sleep"
            resp = requests.get(url, headers=self.headers, params={"limit": 1})
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return data[0] if data else {}
            return {}
        except Exception as e:
            print(f"Oura sleep fetch error: {e}")
            return {}
    
    def get_latest_activity(self):
        """Get today's activity data"""
        try:
            url = f"{self.base_url}/daily_activity"
            resp = requests.get(url, headers=self.headers, params={"limit": 1})
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return data[0] if data else {}
            return {}
        except Exception as e:
            print(f"Oura activity fetch error: {e}")
            return {}
    
    def get_latest_hrv(self):
        """Get latest HRV data"""
        try:
            url = f"{self.base_url}/daily_cardiovascular_age"
            resp = requests.get(url, headers=self.headers, params={"limit": 1})
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return data[0] if data else {}
            return {}
        except Exception as e:
            print(f"Oura HRV fetch error: {e}")
            return {}
    
    def get_range(self, start_date, end_date):
        """Get data for a date range"""
        try:
            readiness_url = f"{self.base_url}/daily_readiness"
            sleep_url = f"{self.base_url}/daily_sleep"
            
            readiness_resp = requests.get(
                readiness_url,
                headers=self.headers,
                params={"start_date": start_date, "end_date": end_date}
            )
            
            sleep_resp = requests.get(
                sleep_url,
                headers=self.headers,
                params={"start_date": start_date, "end_date": end_date}
            )
            
            return {
                "readiness": readiness_resp.json().get("data", []) if readiness_resp.status_code == 200 else [],
                "sleep": sleep_resp.json().get("data", []) if sleep_resp.status_code == 200 else []
            }
        except Exception as e:
            print(f"Oura range fetch error: {e}")
            return {"readiness": [], "sleep": []}
