import requests
from typing import Dict, Any
from config import VIRUSTOTAL_API_KEY
import base64

def _vt_request(endpoint: str, indicator_type: str, indicator: str) -> Dict[str, Any]:
    if not VIRUSTOTAL_API_KEY:
        return {
            "provider": "virustotal",
            "indicator_type": indicator_type,
            "indicator": indicator,
            "status": "error",
            "error_type": "missing_credentials",
            "message": "VIRUSTOTAL_API_KEY not configured."
        }
        
    url = f"https://www.virustotal.com/api/v3/{endpoint}"
    headers = {
        "x-apikey": VIRUSTOTAL_API_KEY
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return {
                "provider": "virustotal",
                "indicator_type": indicator_type,
                "indicator": indicator,
                "status": "ok",
                "data": resp.json()
            }
        elif resp.status_code == 429:
            return {
                "provider": "virustotal",
                "indicator_type": indicator_type,
                "indicator": indicator,
                "status": "error",
                "error_type": "rate_limit",
                "message": "Rate limit exceeded."
            }
        else:
            return {
                "provider": "virustotal",
                "indicator_type": indicator_type,
                "indicator": indicator,
                "status": "error",
                "error_type": "http_error",
                "message": f"HTTP {resp.status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            "provider": "virustotal",
            "indicator_type": indicator_type,
            "indicator": indicator,
            "status": "error",
            "error_type": "timeout",
            "message": "Provider timeout."
        }
    except Exception as e:
        return {
            "provider": "virustotal",
            "indicator_type": indicator_type,
            "indicator": indicator,
            "status": "error",
            "error_type": "unknown",
            "message": str(e)
        }

def enrich_ip(ip: str) -> Dict[str, Any]:
    return _vt_request(f"ip_addresses/{ip}", "ip", ip)

def enrich_domain(domain: str) -> Dict[str, Any]:
    return _vt_request(f"domains/{domain}", "domain", domain)

def enrich_url(url_val: str) -> Dict[str, Any]:
    url_id = base64.urlsafe_b64encode(url_val.encode()).decode().strip("=")
    return _vt_request(f"urls/{url_id}", "url", url_val)

def enrich_hash(file_hash: str) -> Dict[str, Any]:
    return _vt_request(f"files/{file_hash}", "hash", file_hash)
