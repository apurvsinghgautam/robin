# HTTP Backend Configuration

Robin supports two HTTP backends for accessing .onion sites through Tor:

## pycurl (Recommended)

**When to use**: Default choice for accessing .onion sites

**Why pycurl**:
- Uses libcurl (same library as curl command)
- Better compatibility with .onion sites through Tor SOCKS5 proxy
- More reliable connection handling for Tor hidden services
- Proven to work when Python requests fails with connection errors

**Requirements**:
```bash
pip install pycurl
```

## Python requests

**When to use**: If pycurl is not available or causes issues

**Limitations**:
- May encounter "Remote end closed connection" errors with some .onion sites
- Less reliable for Tor hidden service connections
- Works better for clearnet sites

## Configuration

Set in `.env` file:
```bash
# Use pycurl (recommended)
USE_PYCURL=true

# Use requests
USE_PYCURL=false
```

## Technical Details

The issue with Python requests accessing .onion sites appears to be related to how the library handles SOCKS5 proxy connections and HTTP protocol negotiation with Tor hidden services. The curl/libcurl implementation has better compatibility with Tor's SOCKS5 proxy for .onion domains.
