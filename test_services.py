from unittest.mock import patch, Mock
import requests
from services import ipinfo, ip2location, shodan, virustotal, censys

@patch("services.ipinfo.requests.get")
@patch("services.ipinfo.IPINFO_TOKEN", "fake_token")
def test_ipinfo_success(mock_get):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"org": "Google"}
    mock_get.return_value = mock_resp
    
    res = ipinfo.enrich_ip("8.8.8.8")
    assert res["status"] == "ok"
    assert res["data"]["org"] == "Google"

@patch("services.ipinfo.IPINFO_TOKEN", "")
def test_ipinfo_missing_creds():
    res = ipinfo.enrich_ip("8.8.8.8")
    assert res["status"] == "error"
    assert res["error_type"] == "missing_credentials"

@patch("services.ipinfo.requests.get")
@patch("services.ipinfo.IPINFO_TOKEN", "fake_token")
def test_ipinfo_rate_limit(mock_get):
    mock_resp = Mock()
    mock_resp.status_code = 429
    mock_get.return_value = mock_resp
    
    res = ipinfo.enrich_ip("8.8.8.8")
    assert res["status"] == "error"
    assert res["error_type"] == "rate_limit"

@patch("services.ipinfo.requests.get")
@patch("services.ipinfo.IPINFO_TOKEN", "fake_token")
def test_ipinfo_timeout(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout("Timeout")
    
    res = ipinfo.enrich_ip("8.8.8.8")
    assert res["status"] == "error"
    assert res["error_type"] == "timeout"

@patch("services.censys.requests.get")
@patch("services.censys.CENSYS_API_ID", "fake_id")
@patch("services.censys.CENSYS_SECRET", "fake_secret")
def test_censys_success(mock_get):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": "data"}
    mock_get.return_value = mock_resp
    
    res = censys.enrich_domain("example.com")
    assert res["status"] == "ok"
    assert res["data"]["result"] == "data"
    
@patch("services.virustotal.requests.get")
@patch("services.virustotal.VIRUSTOTAL_API_KEY", "fake_key")
def test_virustotal_success(mock_get):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"id": "123"}}
    mock_get.return_value = mock_resp
    
    res = virustotal.enrich_hash("5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8")
    assert res["status"] == "ok"
    assert res["data"]["data"]["id"] == "123"
