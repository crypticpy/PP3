
#!/usr/bin/env python
"""
Script to test the analysis-related API endpoints to understand how to integrate them in the UI.
"""
import os
import sys
import json
import requests
from urllib.parse import urljoin

def format_json(obj):
    """Format JSON for pretty printing"""
    return json.dumps(obj, indent=2)

def test_api_endpoints():
    # Base URL for the API (should match your application's API URL)
    # For local testing
    base_url = "http://localhost:8000"
    
    # API endpoints related to analysis
    endpoints = [
        # Health check to ensure API is running
        {"method": "GET", "url": "/health", "description": "Health check endpoint"},
        
        # Get a list of legislation (to get IDs for testing other endpoints)
        {"method": "GET", "url": "/legislation", "description": "List legislation"},
        
        # Analysis endpoints
        {"method": "GET", "url": "/legislation/1/analysis/history", "description": "Get analysis history for legislation ID 1"},
        {"method": "GET", "url": "/legislation/1", "description": "Get legislation details (including latest analysis) for ID 1"},
        
        # Other potentially relevant endpoints
        {"method": "GET", "url": "/dashboard/impact-summary", "description": "Get impact summary for dashboard"}
    ]
    
    print("\n=== Testing API Endpoints ===\n")
    
    for endpoint in endpoints:
        try:
            url = urljoin(base_url, endpoint["url"])
            print(f"Testing {endpoint['method']} {url} - {endpoint['description']}")
            
            if endpoint["method"] == "GET":
                response = requests.get(url)
            elif endpoint["method"] == "POST":
                response = requests.post(url, json={})
            
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # Only print a summary for brevity if response is large
                if isinstance(data, dict) and len(str(data)) > 500:
                    keys = list(data.keys())
                    print(f"Response keys: {keys}")
                    
                    # If there are items, print the first one as a sample
                    if "items" in data and len(data["items"]) > 0:
                        print("\nSample item:")
                        print(format_json(data["items"][0]))
                else:
                    print("\nResponse:")
                    print(format_json(data))
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error testing endpoint: {e}")
        
        print("\n" + "-" * 50 + "\n")
    
    print("API testing completed.")
    print("Based on the API responses, we can determine how to build our UI components to display analysis data.")

if __name__ == "__main__":
    test_api_endpoints()
