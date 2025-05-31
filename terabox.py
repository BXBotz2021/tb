import re
from pprint import pp
from urllib.parse import parse_qs, urlparse

import requests

from tools import get_formatted_size
from typing import Optional, List  # ✅ For compatibility

# ✅ Match known terabox-like services
def check_url_patterns(url: str) -> bool:
    patterns = [
        r"ww\.mirrobox\.com",
        r"www\.nephobox\.com",
        r"freeterabox\.com",
        r"www\.freeterabox\.com",
        r"1024tera\.com",
        r"4funbox\.co",
        r"www\.4funbox\.com",
        r"mirrobox\.com",
        r"nephobox\.com",
        r"terabox\.app",
        r"terabox\.com",
        r"www\.terabox\.ap",
        r"www\.terabox\.com",
        r"www\.1024tera\.co",
        r"www\.momerybox\.com",
        r"teraboxapp\.com",
        r"momerybox\.com",
        r"tibibox\.com",
        r"www\.tibibox\.com",
        r"www\.teraboxapp\.com",
    ]
    return any(re.search(pattern, url) for pattern in patterns)


# ✅ Extract all matching URLs
def get_urls_from_string(string: str) -> List[str]:
    pattern = r"(https?://\S+)"
    urls = re.findall(pattern, string)
    urls = [url for url in urls if check_url_patterns(url)]
    return urls


# ✅ Extract text between two markers
def find_between(data: str, first: str, last: str) -> Optional[str]:
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except ValueError:
        return None


# ✅ Extract `surl` parameter from URL
def extract_surl_from_url(url: str) -> Optional[str]:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    surl = query_params.get("surl", [])
    return surl[0] if surl else None


# ✅ Main data scraper from saver API
def get_data(url: str) -> Optional[dict]:
    # Replace weird netlocs with known domain
    netloc = urlparse(url).netloc
    url = url.replace(netloc, "1024terabox.com")

    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            return None
        default_thumbnail = find_between(resp.text, 'og:image" content="', '"')
    except Exception:
        return None

    # Setup headers and send request to saver API
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json",
        "Origin": "https://ytshorts.savetube.me",
        "Alt-Used": "ytshorts.savetube.me",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    try:
        response = requests.post(
            "https://ytshorts.savetube.me/api/v1/terabox-downloader",
            headers=headers,
            json={"url": url},
        )
        if response.status_code != 200:
            return None

        json_data = response.json()
        responses = json_data.get("response", [])
        if not responses:
            return None

        resolutions = responses[0].get("resolutions", {})
        download = resolutions.get("Fast Download", "")
        video = resolutions.get("HD Video", "")

        if not video:
            return None

        head = requests.head(video)
        content_length = head.headers.get("Content-Length")
        size_bytes = int(content_length) if content_length else None
        size = get_formatted_size(size_bytes) if size_bytes else None

        content_dispo = head.headers.get("content-disposition", "")
        fname_match = re.findall('filename="(.+)"', content_dispo)
        fname = fname_match[0] if fname_match else None

        # Get redirect for download link
        direct_link = None
        if download:
            try:
                dl_response = requests.head(download, allow_redirects=True)
                direct_link = dl_response.headers.get("location", download)
            except Exception:
                direct_link = download

        return {
            "file_name": fname,
            "link": video,
            "direct_link": direct_link,
            "thumb": default_thumbnail,
            "size": size,
            "sizebytes": size_bytes,
        }

    except Exception:
        return None
