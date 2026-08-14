import requests
from typing import Dict, Any
from config import CENSYS_API_ID, CENSYS_SECRET

def _censys_request(endpoint: str, indicator_type: str, indicator: str) -> Dict[str, Any]:
    if not CENSYS_API_ID or not CENSYS_SECRET:
        return {
            "provider": "censys",
            "indicator_type": indicator_type,
            "indicator": indicator,
            "status": "error",
            "error_type": "missing_credentials",
            "message": "Censys credentials not configured."
        }
        
    url = f"https://search.censys.io/api/v2/{endpoint}"
    try:
        resp = requests.get(url, auth=(CENSYS_API_ID, CENSYS_SECRET), timeout=10)
        if resp.status_code == 200:
            return {
                "provider": "censys",
                "indicator_type": indicator_type,
                "indicator": indicator,
                "status": "ok",
                "data": resp.json()
            }
        elif resp.status_code == 429:
            return {
                "provider": "censys",
                "indicator_type": indicator_type,
                "indicator": indicator,
                "status": "error",
                "error_type": "rate_limit",
                "message": "Rate limit exceeded."
            }
        else:
            return {
                "provider": "censys",
                "indicator_type": indicator_type,
                "indicator": indicator,
                "status": "error",
                "error_type": "http_error",
                "message": f"HTTP {resp.status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            "provider": "censys",
            "indicator_type": indicator_type,
            "indicator": indicator,
            "status": "error",
            "error_type": "timeout",
            "message": "Provider timeout."
        }
    except Exception as e:
        return {
            "provider": "censys",
            "indicator_type": indicator_type,
            "indicator": indicator,
            "status": "error",
            "error_type": "unknown",
            "message": str(e)
        }

def enrich_ip(ip: str) -> Dict[str, Any]:
    return _censys_request(f"hosts/{ip}", "ip", ip)

def enrich_domain(domain: str) -> Dict[str, Any]:
    # In Censys API v2, domains are typically searched via the certs endpoint or hosts search, 
    # but for direct lookup, we can do a search. 
    # To keep it simple and safe for direct indicator query, we use the search endpoint.
    return _censys_request(f"certs/search?q={domain}", "domain", domain)
