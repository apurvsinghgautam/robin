from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Callable
from services import ipinfo, ip2location, shodan, virustotal, censys

MAX_CONCURRENT_CALLS = 10

def enrich_iocs(iocs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """
    Takes a dictionary of deduplicated IOCs categorized by type and
    returns a list of structured enrichment results from configured providers.
    """
    tasks = []
    
    # Capability mapping
    for ip in iocs.get("ip", []):
        tasks.append((ipinfo.enrich_ip, ip))
        tasks.append((ip2location.enrich_ip, ip))
        tasks.append((shodan.enrich_ip, ip))
        tasks.append((censys.enrich_ip, ip))
        tasks.append((virustotal.enrich_ip, ip))
        
    for domain in iocs.get("domain", []):
        tasks.append((virustotal.enrich_domain, domain))
        tasks.append((censys.enrich_domain, domain))
        
    for url in iocs.get("url", []):
        tasks.append((virustotal.enrich_url, url))
        
    for file_hash in iocs.get("hash", []):
        tasks.append((virustotal.enrich_hash, file_hash))
        
    if not tasks:
        return []
        
    results = []
    # Execute concurrently
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CALLS) as executor:
        future_to_task = {executor.submit(func, arg): (func, arg) for func, arg in tasks}
        
        for future in as_completed(future_to_task):
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                # Catch any unexpected exceptions that slipped past the provider's own try/except
                func, arg = future_to_task[future]
                results.append({
                    "provider": func.__module__.split('.')[-1],
                    "indicator": arg,
                    "status": "error",
                    "error_type": "unhandled_exception",
                    "message": str(e)
                })
                
    return results
