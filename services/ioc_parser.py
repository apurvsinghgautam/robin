import re
from typing import Dict, List, Set, Any
from urllib.parse import urlparse

# Regular expressions for IOC extraction
# IPv4 address matching (basic, avoiding false positives by bounded checks)
IP_REGEX = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
# SHA256 hashes
SHA256_REGEX = re.compile(r'\b[a-fA-F0-9]{64}\b')
# URL matching (http/https/ftp)
URL_REGEX = re.compile(r'\b(?:https?|ftp):\/\/[^\s/$.?#].[^\s]*\b', re.IGNORECASE)

def extract_domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc.split(':')[0] if parsed.netloc else ""
    except:
        return ""

# Domain matching (excluding common English words/false positives by requiring TLDs)
# A more robust approach checks against known TLDs, but we'll use a basic pattern.
DOMAIN_REGEX = re.compile(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b')

def _is_valid_ipv4(ip: str) -> bool:
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

def extract_iocs(text: str) -> Dict[str, Set[str]]:
    """
    Extracts IOCs from a given string and returns a dictionary categorized by type.
    """
    if not text:
        return {"ip": set(), "domain": set(), "url": set(), "hash": set()}
    
    iocs = {
        "ip": set(),
        "domain": set(),
        "url": set(),
        "hash": set()
    }
    
    # Extract URLs first so we don't double count domains in URLs
    urls = URL_REGEX.findall(text)
    for url in urls:
        iocs["url"].add(url)
        # Also extract the domain from the URL
        domain = extract_domain_from_url(url)
        if domain and not _is_valid_ipv4(domain):
            iocs["domain"].add(domain.lower())
            
    # Extract IPs
    ips = IP_REGEX.findall(text)
    for ip in ips:
        if _is_valid_ipv4(ip):
            iocs["ip"].add(ip)
            
    # Extract Domains
    domains = DOMAIN_REGEX.findall(text)
    for domain in domains:
        d = domain.lower()
        if not _is_valid_ipv4(d):
            iocs["domain"].add(d)
            
    # Extract Hashes (SHA256)
    hashes = SHA256_REGEX.findall(text)
    for h in hashes:
        iocs["hash"].add(h.lower())
        
    return iocs

def merge_iocs(base: Dict[str, Set[str]], additional: Dict[str, Set[str]]):
    """Merges the additional IOCs into the base dictionary in-place."""
    for k in base.keys():
        base[k].update(additional.get(k, set()))

def extract_all_iocs_from_job_data(query: str, search_results: List[Dict[str, str]] = None, scraped_data: List[Dict[str, str]] = None) -> Dict[str, List[str]]:
    """
    Extracts IOCs from all available sources in a job and returns deduplicated lists.
    """
    master_iocs = {
        "ip": set(),
        "domain": set(),
        "url": set(),
        "hash": set()
    }
    
    # 1. Parse Query
    merge_iocs(master_iocs, extract_iocs(query))
    
    # 2. Parse Search Results
    if search_results:
        for res in search_results:
            merge_iocs(master_iocs, extract_iocs(res.get("title", "")))
            # We usually skip extracting from .onion links, but we can extract if there are standard links
            merge_iocs(master_iocs, extract_iocs(res.get("link", "")))
            
    # 3. Parse Scraped Data
    if scraped_data:
        for scrap in scraped_data:
            merge_iocs(master_iocs, extract_iocs(scrap.get("content", "")))
            
    # Convert sets back to lists
    return {k: list(v) for k, v in master_iocs.items()}
