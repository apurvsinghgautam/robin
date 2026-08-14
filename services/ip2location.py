import requests
from typing import Dict, Any
from config import IP2LOCATION_API_KEY

def enrich_ip(ip: str) -> Dict[str, Any]:
    if not IP2LOCATION_API_KEY:
        return {
            "provider": "ip2location",
            "indicator_type": "ip",
            "indicator": ip,
            "status": "error",
            "error_type": "missing_credentials",
            "message": "IP2LOCATION_API_KEY not configured."
        }
        
    url = f"https://api.ip2location.io/?key={IP2LOCATION_API_KEY}&ip={ip}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return {
                "provider": "ip2location",
                "indicator_type": "ip",
                "indicator": ip,
                "status": "ok",
                "data": resp.json()
            }
        elif resp.status_code == 429:
            return {
                "provider": "ip2location",
                "indicator_type": "ip",
                "indicator": ip,
                "status": "error",
                "error_type": "rate_limit",
                "message": "Rate limit exceeded."
            }
        else:
            return {
                "provider": "ip2location",
                "indicator_type": "ip",
                "indicator": ip,
                "status": "error",
                "error_type": "http_error",
                "message": f"HTTP {resp.status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            "provider": "ip2location",
            "indicator_type": "ip",
            "indicator": ip,
            "status": "error",
            "error_type": "timeout",
            "message": "Provider timeout."
        }
    except Exception as e:
        return {
            "provider": "ip2location",
            "indicator_type": "ip",
            "indicator": ip,
            "status": "error",
            "error_type": "unknown",
            "message": str(e)
        }
