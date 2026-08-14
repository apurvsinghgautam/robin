import requests
from typing import Dict, Any
from config import IPINFO_TOKEN

def enrich_ip(ip: str) -> Dict[str, Any]:
    if not IPINFO_TOKEN:
        return {
            "provider": "ipinfo",
            "indicator_type": "ip",
            "indicator": ip,
            "status": "error",
            "error_type": "missing_credentials",
            "message": "IPINFO_TOKEN not configured."
        }
        
    url = f"https://ipinfo.io/{ip}/json?token={IPINFO_TOKEN}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return {
                "provider": "ipinfo",
                "indicator_type": "ip",
                "indicator": ip,
                "status": "ok",
                "data": resp.json()
            }
        elif resp.status_code == 429:
            return {
                "provider": "ipinfo",
                "indicator_type": "ip",
                "indicator": ip,
                "status": "error",
                "error_type": "rate_limit",
                "message": "Rate limit exceeded."
            }
        else:
            return {
                "provider": "ipinfo",
                "indicator_type": "ip",
                "indicator": ip,
                "status": "error",
                "error_type": "http_error",
                "message": f"HTTP {resp.status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            "provider": "ipinfo",
            "indicator_type": "ip",
            "indicator": ip,
            "status": "error",
            "error_type": "timeout",
            "message": "Provider timeout."
        }
    except Exception as e:
        return {
            "provider": "ipinfo",
            "indicator_type": "ip",
            "indicator": ip,
            "status": "error",
            "error_type": "unknown",
            "message": str(e)
        }
