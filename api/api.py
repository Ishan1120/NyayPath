import requests
import os

# Get a free API key from serper.dev
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

def search_department_details(department_name, city):
    """Fetches real RTI address info using a Search API"""
    if not SERPER_API_KEY:
        return "Address details not available."

    url = "https://google.serper.dev/search"
    payload = {
        "q": f"official RTI address Public Information Officer {department_name} {city}",
        "num": 3
    }
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        results = response.json()
        snippets = [item.get('snippet', '') for item in results.get('organic', [])]
        return "\n".join(snippets)
    except Exception as e:
        return "Could not fetch address dynamically."

def resolveDepartment(case_id, department_name, city):
    address_context = search_department_details(department_name, city)
    return {"address": address_context, "name": department_name}
