import http.server
import json
import urllib.request
import urllib.parse
import urllib.error
import os
import csv
import subprocess
import shutil
import re
import threading
import time
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import socket

def validate_url(url):
    """Reject SSRF: must be http/https to a public, non-private IP."""
    if not url:
        return False, "URL darf nicht leer sein."
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ('http', 'https'):
        return False, f"Protokoll '{scheme}' ist nicht erlaubt. Nur http und https werden unterstützt."
    hostname = parsed.hostname or ''
    # Block localhost and obvious internal names
    if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]'):
        return False, "Zugriff auf lokale Adressen ist nicht erlaubt."
    if hostname.endswith('.local') or hostname.endswith('.internal'):
        return False, "Zugriff auf interne Hostnamen ist nicht erlaubt."
    # If hostname is an IP literal, check against private ranges
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False, "Zugriff auf private IP-Adressen ist nicht erlaubt."
        return True, None
    except ValueError:
        pass  # not an IP literal — resolve it
    # Resolve DNS and check the resolved IPs
    try:
        addrs = socket.getaddrinfo(hostname, None)
        seen = set()
        for family, type_, proto, canon, sockaddr in addrs:
            ip_str = sockaddr[0]
            if ip_str in seen:
                continue
            seen.add(ip_str)
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False, f"Die Adresse {hostname} zeigt auf ein privates Netzwerk ({ip_str})."
        return True, None
    except socket.gaierror:
        return False, f"Die Adresse {hostname} konnte nicht aufgelöst werden."
    except Exception as e:
        return False, f"Adressprüfung fehlgeschlagen: {e}"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(os.path.expanduser('~/.cache'), 'stats-sheets')
VENV_DIR = os.path.join(CACHE_DIR, 'venv')
VENV_KAGGLE = os.path.join(VENV_DIR, 'bin', 'kaggle')
RDATASETS_CSV = os.path.join(CACHE_DIR, 'rdatasets.csv')
RDATASETS_MAX_AGE = 86400  # 1 day

_USER_HOME = os.path.expanduser('~')
DENIED_PREFIXES = [
    '/etc', '/bin', '/sbin', '/boot', '/dev', '/proc', '/sys', '/lib', '/lib64', '/lost+found', '/root',
]
USER_DENIED_PREFIXES = [
    os.path.join(_USER_HOME, '.ssh'),
    os.path.join(_USER_HOME, '.config'),
    os.path.join(_USER_HOME, '.gnupg'),
    os.path.join(_USER_HOME, '.aws'),
    os.path.join(_USER_HOME, '.azure'),
    os.path.join(_USER_HOME, '.kaggle'),
    os.path.join(_USER_HOME, '.docker'),
    os.path.join(_USER_HOME, '.netrc'),
    os.path.join(_USER_HOME, '.local', 'share'),
]


def is_denied_download_dir(target_dir):
    """Return True if target_dir is a blocked system or sensitive user path."""
    for prefix in DENIED_PREFIXES + USER_DENIED_PREFIXES:
        if target_dir == prefix or target_dir.startswith(prefix + '/'):
            return True
    return False


def has_invalid_download_path_chars(target_dir):
    """Reject characters that break R string syntax or enable injection."""
    return "'" in target_dir or '\\' in target_dir

# Heartbeat watchdog
last_heartbeat = time.time()
HEARTBEAT_TIMEOUT = 30

# Rate limiting
_request_log = defaultdict(list)
_rate_limit_lock = threading.Lock()
RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW = 60

rdatasets_cache = []
rdatasets_cached_at = None
R_AVAILABLE = False
PARQUET_AVAILABLE = False

def check_r_available():
    global R_AVAILABLE
    try:
        result = subprocess.run(['Rscript', '--version'], capture_output=True, timeout=5)
        R_AVAILABLE = (result.returncode == 0)
    except Exception:
        R_AVAILABLE = False

def check_parquet_available():
    global PARQUET_AVAILABLE
    try:
        import pyarrow.parquet as pq
        import pyarrow as pa
        pq, pa  # verify
        PARQUET_AVAILABLE = True
        return
    except ImportError:
        pass
    try:
        import pandas as pd
        pd.read_parquet  # verify
        PARQUET_AVAILABLE = True
        return
    except Exception:
        PARQUET_AVAILABLE = False

def ensure_kaggle_venv():
    if os.path.exists(VENV_KAGGLE):
        return True
    print("Creating venv for Kaggle CLI...")
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        subprocess.run([sys.executable, '-m', 'venv', VENV_DIR], check=True, capture_output=True)
        pip = os.path.join(VENV_DIR, 'bin', 'pip')
        subprocess.run([pip, 'install', 'kaggle'], check=True, capture_output=True)
        print("Kaggle venv created.")
        return True
    except Exception as e:
        print(f"Warning: Could not set up Kaggle venv: {e}")
        return False

def load_rdatasets():
    global rdatasets_cache, rdatasets_cached_at
    csv_path = RDATASETS_CSV

    should_download = not os.path.exists(csv_path)
    if os.path.exists(csv_path):
        age = time.time() - os.path.getmtime(csv_path)
        if age > RDATASETS_MAX_AGE:
            print(f"Rdatasets cache is {age/86400:.0f} days old, refreshing...")
            should_download = True

    if should_download:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            print("Downloading Rdatasets catalog...")
            req = urllib.request.Request(
                'https://vincentarelbundock.github.io/Rdatasets/datasets.csv',
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response, open(csv_path, 'wb') as f:
                f.write(response.read())
        except Exception as e:
            print(f"Error downloading Rdatasets catalog: {e}")
            if os.path.exists(csv_path):
                print("Falling back to existing cache.")
            else:
                return
    
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rdatasets_cache = list(reader)
                rdatasets_cached_at = os.path.getmtime(csv_path)
                print(f"Loaded {len(rdatasets_cache)} Rdatasets.")
        except Exception as e:
            print(f"Error parsing Rdatasets CSV: {e}")

def is_rate_limited(ip):
    now = time.time()
    with _rate_limit_lock:
        window = _request_log[ip]
        while window and window[0] < now - RATE_LIMIT_WINDOW:
            window.pop(0)
        if len(window) >= RATE_LIMIT_MAX:
            return True
        window.append(now)
        return False

class ThreadPoolHTTPServer(http.server.ThreadingHTTPServer):
    def __init__(self, *args, max_workers=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def process_request(self, request, client_address):
        self.executor.submit(self._threaded_process_request, request, client_address)

    def _threaded_process_request(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

def get_url_size(url):
    ok, _ = validate_url(url)
    if not ok:
        return None
    # Try HEAD first
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            content_length = response.getheader('Content-Length')
            if content_length:
                return int(content_length)
    except Exception as e:
        print(f"HEAD size check failed for {url}: {e}")
    # Fallback: GET with Range to avoid full download
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Range': 'bytes=0-0'
        })
        with urllib.request.urlopen(req, timeout=5) as response:
            content_range = response.getheader('Content-Range')
            if content_range:
                total = content_range.split('/')[-1]
                if total.isdigit():
                    return int(total)
            content_length = response.getheader('Content-Length')
            if content_length:
                return int(content_length)
    except Exception as e:
        print(f"Range size check failed for {url}: {e}")
    # Last resort: GET headers only via opening and closing
    try:
        req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            content_length = response.getheader('Content-Length')
            if content_length:
                return int(content_length)
    except Exception as e:
        print(f"GET size check failed for {url}: {e}")
    return None

def preview_parquet_url(url, max_rows=10):
    if not PARQUET_AVAILABLE:
        return None, "Parquet preview is not available — install pyarrow or pandas"
    ok, _ = validate_url(url)
    if not ok:
        return None, "Ungültige URL."
    tmp = None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
        tmp = os.path.join('/tmp', f'parquet_preview_{threading.get_ident()}.parquet')
        with open(tmp, 'wb') as f:
            f.write(raw)
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(tmp)
            columns = table.column_names
            rows = []
            for i in range(min(max_rows, table.num_rows)):
                row = {}
                for col in columns:
                    val = table.column(col)[i].as_py()
                    if hasattr(val, '__len__') and not isinstance(val, (str, bytes)):
                        val = str(val)
                    row[col] = val
                rows.append(row)
            return {"columns": columns, "rows": rows}, None
        except ImportError:
            import pandas as pd
            df = pd.read_parquet(tmp)
            columns = list(df.columns)
            rows = []
            for _, row in df.head(max_rows).iterrows():
                r = {}
                for col in columns:
                    val = row[col]
                    if hasattr(val, '__len__') and not isinstance(val, (str, bytes)):
                        val = str(val)
                    elif pd.isna(val):
                        val = None
                    r[col] = val
                rows.append(r)
            return {"columns": columns, "rows": rows}, None
    except Exception as e:
        return None, str(e)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)

def parquet_to_csv(parquet_path, csv_path):
    """Convert a local parquet file to a CSV file. Returns True on success."""
    if not PARQUET_AVAILABLE:
        return False
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(parquet_path)
        import pyarrow.csv as pcsv
        pcsv.write_csv(table, csv_path)
        return True
    except ImportError:
        pass
    try:
        import pandas as pd
        df = pd.read_parquet(parquet_path)
        df.to_csv(csv_path, index=False)
        return True
    except Exception:
        return False

def trim_truncated(raw_bytes):
    """Decode bytes and discard the last potentially-truncated line."""
    try:
        raw = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raw = raw_bytes.decode('utf-8', errors='replace')
        if raw and raw[-1] == '\ufffd':
            raw = raw[:-1]
    # Find last complete line
    last_nl = raw.rfind('\n')
    if last_nl >= 0:
        raw = raw[:last_nl]
    return raw

STATIC_ROUTES = {
    '/': 'index.html',
    '/index.html': 'index.html',
    '/script.js': 'script.js',
    '/styles.css': 'styles.css',
    '/cheat-sheet-data.json': 'cheat-sheet-data.json',
    '/icon.svg': 'assets/icon.svg',
    '/favicon.ico': 'assets/icon.svg',
}

CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
}


def resolve_static_path(url_path):
    """Map URL path to a file under BASE_DIR. Returns None if not allowed."""
    rel = STATIC_ROUTES.get(url_path)
    if not rel:
        return None
    file_path = os.path.normpath(os.path.join(BASE_DIR, rel))
    if not file_path.startswith(BASE_DIR) or not os.path.isfile(file_path):
        return None
    return file_path

ALLOWED_ORIGINS = ('null', '', 'file://')

class Handler(http.server.BaseHTTPRequestHandler):
    def _check_origin(self):
        origin = self.headers.get('Origin', '')
        if origin in ALLOWED_ORIGINS:
            return True
        
        # Allow any localhost/127.0.0.1 origin regardless of port
        try:
            parsed = urllib.parse.urlparse(origin)
            if parsed.hostname in ('localhost', '127.0.0.1'):
                return True
        except Exception:
            pass
            
        self.send_error_response("Zugriff verweigert: Unerlaubter Origin.", code=403)
        return False

    def _serve_static(self, url_path):
        file_path = resolve_static_path(url_path)
        if not file_path:
            self.send_error_response("Endpoint nicht gefunden", code=404)
            return
        ext = os.path.splitext(file_path)[1].lower()
        content_type = CONTENT_TYPES.get(ext, 'application/octet-stream')
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error_response(str(e), code=500)

    def do_OPTIONS(self):
        if not self._check_origin():
            return
        self.send_response(200)
        origin = self.headers.get('Origin', '')
        self.send_header('Access-Control-Allow-Origin', origin if origin else '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path in STATIC_ROUTES:
            self._serve_static(parsed_path.path)
            return
        if not self._check_origin():
            return
        if self.path not in ('/heartbeat', '/config') and is_rate_limited(self.client_address[0]):
            self.send_error_response("Too many requests", code=429)
            return
        params = urllib.parse.parse_qs(parsed_path.query)

        if parsed_path.path == '/search':
            query = params.get('q', [''])[0].strip().lower()
            source = params.get('source', ['all'])[0].strip().lower()
            try:
                page = max(1, int(params.get('page', ['1'])[0]))
            except ValueError:
                page = 1
            try:
                per_page = max(1, min(100, int(params.get('per_page', ['25'])[0])))
            except ValueError:
                per_page = 25

            results = []
            kaggle_skipped = False
            rdatasets_total = 0
            hf_total = 0
            kaggle_total = 0

            # --- Rdatasets (local, collect all matches) ---
            if source in ('all', 'rdatasets') and rdatasets_cache:
                for row in rdatasets_cache:
                    if query:
                        item = row.get('Item', '')
                        title = row.get('Title', '')
                        package = row.get('Package', '')
                        match = (query in item.lower() or
                                 query in title.lower() or
                                 query in package.lower())
                        if not match:
                            continue
                    results.append({
                        "id": f"rdatasets:{row['Package']}:{row['Item']}",
                        "name": row.get('Item', ''),
                        "source": "rdatasets",
                        "package": row.get('Package', ''),
                        "item": row.get('Item', ''),
                        "title": row.get('Title', ''),
                        "rows": int(row['Rows']) if row.get('Rows') else None,
                        "cols": int(row['Cols']) if row.get('Cols') else None,
                        "url": row.get('CSV', ''),
                        "doc_url": row.get('Doc', '')
                    })
                rdatasets_total = len(results)

            # --- Hugging Face (remote API — no page param, fetch max 100 results) ---
            if source in ('all', 'huggingface'):
                try:
                    hf_url = "https://huggingface.co/api/datasets?limit=100"
                    if query:
                        hf_url += f"&search={urllib.parse.quote(query)}"
                    req = urllib.request.Request(hf_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        hf_data = json.loads(response.read().decode('utf-8'))
                        for item in hf_data:
                            results.append({
                                "id": f"hf:{item['id']}",
                                "name": item['id'].split('/')[-1] if '/' in item['id'] else item['id'],
                                "source": "huggingface",
                                "package": item['id'].split('/')[0] if '/' in item['id'] else "huggingface",
                                "item": item['id'],
                                "title": item.get('description', '').strip() or f"Hugging Face dataset repository: {item['id']}",
                                "rows": None,
                                "cols": None,
                                "url": f"https://huggingface.co/datasets/{item['id']}",
                                "downloads": item.get('downloads', 0),
                                "likes": item.get('likes', 0)
                            })
                        hf_total = len(hf_data)
                except Exception as e:
                    print(f"HF fetch error: {e}")

            # --- Kaggle (local CLI, collect all) ---
            if source in ('all', 'kaggle'):
                kaggle_json = os.path.expanduser('~/.kaggle/kaggle.json')
                kaggle_token = os.path.expanduser('~/.kaggle/access_token')
                if not os.path.exists(kaggle_json) and not os.path.exists(kaggle_token):
                    kaggle_skipped = True
                    if source == 'kaggle':
                        self.send_success_response({"needs_auth": True})
                        return
                else:
                    try:
                        env = os.environ.copy()
                        kaggle_cmd = [VENV_KAGGLE, 'datasets', 'list', '--csv']
                        if query:
                            kaggle_cmd = [VENV_KAGGLE, 'datasets', 'list', '-s', query, '--csv']
                        result = subprocess.run(kaggle_cmd, capture_output=True, text=True, env=env)
                        if result.returncode == 0:
                            lines = result.stdout.splitlines()
                            if lines:
                                reader = csv.DictReader(lines)
                                for row in reader:
                                    results.append({
                                        "id": f"kaggle:{row.get('ref', '')}",
                                        "name": row.get('title', ''),
                                        "source": "kaggle",
                                        "package": row.get('ref', '').split('/')[0] if '/' in row.get('ref', '') else '',
                                        "item": row.get('ref', ''),
                                        "title": row.get('subtitle', ''),
                                        "rows": None,
                                        "cols": None,
                                        "url": f"https://www.kaggle.com/datasets/{row.get('ref', '')}",
                                        "downloads": int(row.get('downloadCount', 0)) if row.get('downloadCount', '').isdigit() else 0,
                                        "size": row.get('size', '')
                                    })
                        else:
                            if "Authentication required" in result.stdout or "Authentication required" in result.stderr:
                                if source == 'kaggle':
                                    self.send_success_response({"needs_auth": True})
                                    return
                    except Exception as e:
                        print(f"Kaggle fetch error: {e}")
                kaggle_total = len(results) - rdatasets_total - hf_total
                if kaggle_total < 0:
                    kaggle_total = 0

            for r in results:
                r['previewable'] = True

            total = len(results)
            start = (page - 1) * per_page
            end = start + per_page
            page_results = results[start:end]
            total_pages = (total + per_page - 1) // per_page if total else 1

            self.send_success_response({
                "results": page_results,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "kaggle_skipped": kaggle_skipped,
                "has_more": end < total
            })
            
        elif parsed_path.path == '/hf_files':
            dataset_id = params.get('dataset_id', [''])[0].strip()
            if not dataset_id:
                self.send_error_response("dataset_id parameter is required")
                return

            data_files = []
            api_parquet = False
            try:
                req = urllib.request.Request(
                    f"https://huggingface.co/api/datasets/{dataset_id}",
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    meta = json.loads(response.read().decode('utf-8'))
                    for sib in meta.get('siblings', []):
                        p = sib.get('rfilename', '')
                        if p.lower().endswith('.parquet'):
                            api_parquet = True
            except Exception:
                pass

            try:
                req = urllib.request.Request(
                    f"https://huggingface.co/api/datasets/{dataset_id}/tree/main",
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    files_data = json.loads(response.read().decode('utf-8'))

                    valid_extensions = ('.csv', '.tsv', '.json', '.jsonl', '.xlsx', '.txt', '.parquet')
                    for f in files_data:
                        if f.get('type') == 'file' and any(f.get('path', '').lower().endswith(ext) for ext in valid_extensions):
                            data_files.append({
                                "path": f.get('path'),
                                "size": f.get('size')
                            })
            except Exception:
                pass

            if not data_files and api_parquet and not PARQUET_AVAILABLE:
                self.send_success_response({"files": [], "parquet_only": True})
            elif not data_files:
                self.send_success_response({"files": [], "parquet_only": False})
            else:
                self.send_success_response({"files": data_files, "parquet_only": False})
        elif parsed_path.path == '/url_size':
            url = params.get('url', [''])[0].strip()
            if not url:
                self.send_error_response("url parameter is required")
                return
            ok, err = validate_url(url)
            if not ok:
                self.send_error_response(err)
                return
            size = get_url_size(url)
            self.send_success_response({"size": size})
        elif parsed_path.path == '/preview':
            url = params.get('url', [''])[0].strip()
            if not url:
                self.send_error_response("url parameter is required")
                return
            if not url.startswith('kaggle:'):
                ok, err = validate_url(url)
                if not ok:
                    self.send_error_response(err)
                    return
            if url.startswith('kaggle:'):
                try:
                    dataset_ref = url.split('kaggle:')[1]
                    tmpdir = os.path.join('/tmp', f'kaggle_preview_{threading.get_ident()}')
                    if os.path.exists(tmpdir):
                        shutil.rmtree(tmpdir)
                    os.makedirs(tmpdir, exist_ok=True)

                    result = subprocess.run([VENV_KAGGLE, 'datasets', 'download', '-d', dataset_ref, '-p', tmpdir, '--unzip'], capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        shutil.rmtree(tmpdir, ignore_errors=True)
                        err = (result.stderr.strip() or result.stdout.strip())
                        if '403' in err:
                            self.send_success_response({"error": "Kaggle-Download nicht erlaubt. Möglicherweise müssen die Nutzungsbedingungen für dieses Dataset auf kaggle.com akzeptiert werden."})
                        else:
                            self.send_success_response({"error": err})
                        return

                    csv_files = []
                    for root, dirs, files in os.walk(tmpdir):
                        for file in files:
                            if file.lower().endswith('.csv'):
                                csv_files.append(os.path.join(root, file))

                    if not csv_files:
                        shutil.rmtree(tmpdir, ignore_errors=True)
                        self.send_success_response({"rows": [], "columns": []})
                        return

                    with open(csv_files[0], 'r', encoding='utf-8', errors='replace') as f:
                        reader = csv.DictReader(f)
                        rows = []
                        for i, row in enumerate(reader):
                            if i >= 10:
                                break
                            rows.append(row)
                        columns = list(rows[0].keys()) if rows else []

                    shutil.rmtree(tmpdir, ignore_errors=True)
                    self.send_success_response({"rows": rows, "columns": columns})
                except subprocess.TimeoutExpired:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    self.send_success_response({"error": "Kaggle-Download dauert zu lange."})
                except Exception as e:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    self.send_success_response({"error": str(e)})
                return

            ext = url.lower().rsplit('.', 1)[-1] if '.' in url else ''

            if ext == 'parquet':
                result, err = preview_parquet_url(url)
                if err:
                    self.send_success_response({"error": err})
                else:
                    self.send_success_response(result)
                return

            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Range': 'bytes=0-65535'
                })
                with urllib.request.urlopen(req, timeout=10) as response:
                    raw_bytes = response.read()
                clean = trim_truncated(raw_bytes)
                lines = clean.splitlines()
                total_chars = len(clean)

                if ext in ('json',):
                    rows = []
                    columns = []

                    # Try fetching a larger window for JSON structure
                    raw_json = clean
                    try:
                        req = urllib.request.Request(url, headers={
                            'User-Agent': 'Mozilla/5.0',
                            'Range': f'bytes=0-{min(1048575, total_chars + 65535)}'
                        })
                        with urllib.request.urlopen(req, timeout=10) as response:
                            bigger = response.read()
                            raw_json = trim_truncated(bigger)
                    except Exception:
                        pass

                    try:
                        data = json.loads(raw_json)
                    except json.JSONDecodeError:
                        data = None

                    if isinstance(data, list):
                        for item in data[:10]:
                            if isinstance(item, dict):
                                rows.append(item)
                        if rows:
                            columns = list(rows[0].keys())
                    elif isinstance(data, dict):
                        row = {}
                        for k, v in data.items():
                            if isinstance(v, list):
                                row[k] = f"[{len(v)} items]"
                            elif isinstance(v, dict):
                                row[k] = f"{{{', '.join(list(v.keys())[:3])}}}" if v else "{}"
                            elif isinstance(v, (str, int, float, bool)):
                                vs = str(v)
                                row[k] = vs[:80] + '...' if len(vs) > 80 else vs
                            else:
                                row[k] = str(v) if v is not None else ''
                        if row:
                            rows.append(row)
                            columns = list(row.keys())
                    else:
                        # Try extracting complete JSON objects from truncated content
                        text = raw_json
                        decoder = json.JSONDecoder()
                        # If it starts with '[', skip the bracket
                        idx = text.index('[') + 1 if text.strip().startswith('[') else 0
                        while idx < len(text) and len(rows) < 10:
                            while idx < len(text) and text[idx] in ' \t\n\r,':
                                idx += 1
                            if idx >= len(text):
                                break
                            try:
                                obj, pos = decoder.raw_decode(text, idx)
                            except json.JSONDecodeError:
                                break
                            if isinstance(obj, dict):
                                rows.append(obj)
                                if not columns:
                                    columns = list(obj.keys())
                            idx = pos
                        # If raw_decode got nothing, try line-by-line
                        if not rows:
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    obj = json.loads(line)
                                except json.JSONDecodeError:
                                    continue
                                if isinstance(obj, dict):
                                    rows.append(obj)
                                    if not columns:
                                        columns = list(obj.keys())
                                if len(rows) >= 10:
                                    break
                    self.send_success_response({"rows": rows, "columns": columns})
                    return

                if ext in ('jsonl',):
                    rows = []
                    columns = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(obj, dict):
                            rows.append(obj)
                            if not columns:
                                columns = list(obj.keys())
                        if len(rows) >= 10:
                            break
                    self.send_success_response({"rows": rows, "columns": columns})
                    return

                if len(lines) < 2:
                    self.send_success_response({"rows": [], "columns": []})
                    return
                delimiter = '\t' if ext == 'tsv' else ','
                reader = csv.DictReader(lines, delimiter=delimiter)
                rows = []
                for i, row in enumerate(reader):
                    if i >= 10:
                        break
                    rows.append(row)
                columns = list(rows[0].keys()) if rows else []
                self.send_success_response({"rows": rows, "columns": columns})
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    self.send_success_response({"error": "Zugriff verweigert (401). Der Datensatz ist möglicherweise privat oder erfordert eine Authentifizierung."})
                else:
                    self.send_success_response({"error": str(e)})
            except Exception as e:
                self.send_error_response(str(e))
        elif parsed_path.path == '/translations':
            lang = params.get('lang', ['en'])[0].strip()
            file_path = os.path.join(BASE_DIR, f'{lang}.json')
            if not os.path.exists(file_path):
                self.send_error_response(f"Translations for '{lang}' not found")
                return
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.send_success_response(json.load(f))
            except Exception as e:
                self.send_error_response(str(e))
        elif parsed_path.path == '/cheat-sheet':
            file_path = os.path.join(BASE_DIR, 'cheat-sheet-data.json')
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.send_success_response(json.load(f))
            except Exception as e:
                self.send_error_response(str(e))
        elif parsed_path.path == '/config':
            def get_xdg_dir(name, fallback):
                try:
                    result = subprocess.run(['xdg-user-dir', name], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        path = result.stdout.strip()
                        if path:
                            return path
                except Exception:
                    pass
                return os.path.expanduser(fallback)
            self.send_success_response({
                "r_available": R_AVAILABLE,
                "parquet_available": PARQUET_AVAILABLE,
                "downloads_dir": get_xdg_dir('DOWNLOAD', '~/Downloads'),
                "documents_dir": get_xdg_dir('DOCUMENTS', '~/Documents'),
                "rdatasets_cached_at": rdatasets_cached_at,
            })
        elif parsed_path.path == '/heartbeat':
            global last_heartbeat
            last_heartbeat = time.time()
            self.send_success_response({"ok": True})
        else:
            self.send_error_response("Endpoint nicht gefunden", code=404)

    def do_POST(self):
        if not self._check_origin():
            return
        if is_rate_limited(self.client_address[0]):
            self.send_error_response("Too many requests", code=429)
            return
        if self.path == '/download':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            url = data.get('url')
            dataset_name = data.get('dataset_name', 'dataset').strip()
            format_type = data.get('format', 'csv').strip().lower()
            target_dir = data.get('target_dir', '').strip()
            
            if format_type in ('rdata', 'rds') and not R_AVAILABLE:
                self.send_error_response("R ist auf dem Server nicht verfügbar. RData/RDS-Export ist deaktiviert.")
                return
            
            if not url:
                self.send_error_response("URL-Parameter fehlt.")
                return

            if not url.startswith('kaggle:'):
                ok, err = validate_url(url)
                if not ok:
                    self.send_error_response(err)
                    return
            
            # Validate and sanitize dataset_name
            safe_name = re.sub(r'[^\w\s.-]', '', dataset_name).strip()
            if not safe_name:
                safe_name = 'dataset'
            dataset_name = safe_name
            
            if target_dir.startswith('~'):
                target_dir = os.path.expanduser(target_dir)
            if not target_dir:
                try:
                    result = subprocess.run(['xdg-user-dir', 'DOWNLOAD'], capture_output=True, text=True, timeout=2)
                    target_dir = result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else os.path.expanduser('~/Downloads')
                except Exception:
                    target_dir = os.path.expanduser('~/Downloads')

            target_dir = os.path.abspath(target_dir)
            if not os.path.isabs(target_dir):
                self.send_error_response("Zielordner muss ein absoluter Pfad sein.")
                return

            if has_invalid_download_path_chars(target_dir):
                self.send_error_response("Zielordner enthält ungültige Zeichen.")
                return

            if is_denied_download_dir(target_dir):
                self.send_error_response("Dieses Verzeichnis ist als Ziel nicht erlaubt.")
                return

            # Security: validate directory actually exists and is writable
            if not os.path.isdir(target_dir):
                self.send_error_response("Zielordner existiert nicht.")
                return
            if not os.access(target_dir, os.W_OK | os.X_OK):
                self.send_error_response("Keine Schreibrechte für den Zielordner.")
                return
            
            ext = ".csv"
            if url.lower().endswith('.json'):
                ext = ".json"
            elif url.lower().endswith('.tsv'):
                ext = ".tsv"
            elif url.lower().endswith('.parquet'):
                ext = ".parquet"
                
            temp_file_path = os.path.join(target_dir, f"temp_{dataset_name}{ext}")
            
            try:
                os.makedirs(target_dir, exist_ok=True)
                
                # 1. Download file to temp
                if url.startswith('kaggle:'):
                    dataset_ref = url.split('kaggle:')[1]
                    download_dir = os.path.join(target_dir, f"kaggle_temp_{dataset_name}")
                    os.makedirs(download_dir, exist_ok=True)

                    result = subprocess.run([VENV_KAGGLE, 'datasets', 'download', '-d', dataset_ref, '-p', download_dir, '--unzip'], capture_output=True, text=True)
                    if result.returncode != 0:
                        shutil.rmtree(download_dir, ignore_errors=True)
                        raise Exception(f"Kaggle Download Fehler: {result.stderr.strip()} {result.stdout.strip()}")

                    # Count extracted files
                    all_files = []
                    for root, dirs, files in os.walk(download_dir):
                        for file in files:
                            all_files.append(os.path.join(root, file))

                    if not all_files:
                        shutil.rmtree(download_dir, ignore_errors=True)
                        raise Exception("Kaggle-Datensatz enthält keine Dateien.")

                    # Single file: keep old behavior (direct save)
                    if len(all_files) == 1:
                        shutil.move(all_files[0], temp_file_path)
                        shutil.rmtree(download_dir, ignore_errors=True)
                        ext = ".csv" if all_files[0].lower().endswith('.csv') else ext
                    else:
                        # Multiple files: preserve entire dataset in a subdirectory
                        dataset_dir = os.path.join(target_dir, dataset_name)
                        os.makedirs(dataset_dir, exist_ok=True)
                        for f in all_files:
                            rel = os.path.relpath(f, download_dir)
                            dst = os.path.join(dataset_dir, rel)
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.move(f, dst)
                        shutil.rmtree(download_dir, ignore_errors=True)

                        self.send_success_response({
                            "message": f"Dataset heruntergeladen ({len(all_files)} Dateien in {dataset_name}/)",
                            "file_path": dataset_dir
                        })
                        return
                else:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response, open(temp_file_path, 'wb') as out_file:
                        out_file.write(response.read())
                
                # 2. Handle conversion and output
                if ext == '.parquet':
                    if format_type == 'csv':
                        final_path = os.path.join(target_dir, f"{dataset_name}.csv")
                        if not parquet_to_csv(temp_file_path, final_path):
                            raise Exception("Parquet-Konvertierung fehlgeschlagen.")
                        os.remove(temp_file_path)
                    elif format_type == 'json':
                        csv_tmp = temp_file_path + '_conv.csv'
                        final_path = os.path.join(target_dir, f"{dataset_name}.json")
                        if not parquet_to_csv(temp_file_path, csv_tmp):
                            raise Exception("Parquet-Konvertierung fehlgeschlagen.")
                        rows = []
                        with open(csv_tmp, mode='r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                rows.append(row)
                        os.remove(csv_tmp)
                        with open(final_path, mode='w', encoding='utf-8') as f:
                            json.dump(rows, f, indent=2, ensure_ascii=False)
                        os.remove(temp_file_path)
                    elif format_type in ('rdata', 'rds'):
                        csv_tmp = temp_file_path + '_conv.csv'
                        final_ext = ".RData" if format_type == "rdata" else ".rds"
                        final_path = os.path.join(target_dir, f"{dataset_name}{final_ext}")
                        if not parquet_to_csv(temp_file_path, csv_tmp):
                            raise Exception("Parquet-Konvertierung fehlgeschlagen.")
                        os.remove(temp_file_path)
                        r_command = (
                            "args <- commandArgs(trailingOnly=TRUE); "
                            "df <- read.csv(args[1], stringsAsFactors=FALSE); "
                            f"{'save(df, file=args[2])' if format_type == 'rdata' else 'saveRDS(df, file=args[2])'}"
                        )
                        result = subprocess.run(
                            ["Rscript", "-e", r_command, csv_tmp, final_path],
                            capture_output=True, text=True
                        )
                        os.remove(csv_tmp)
                        if result.returncode != 0:
                            raise Exception(f"Rscript Fehler: {result.stderr.strip()}")
                    else:
                        raise Exception("Ungültiges Format ausgewählt.")
                elif format_type == 'csv':
                    final_path = os.path.join(target_dir, f"{dataset_name}.csv")
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    os.rename(temp_file_path, final_path)
                    
                elif format_type == 'json':
                    final_path = os.path.join(target_dir, f"{dataset_name}.json")
                    rows = []
                    delimiter = '\t' if ext == '.tsv' else ','
                    with open(temp_file_path, mode='r', encoding='utf-8') as f:
                        reader = csv.DictReader(f, delimiter=delimiter)
                        for row in reader:
                            rows.append(row)
                    with open(final_path, mode='w', encoding='utf-8') as f:
                        json.dump(rows, f, indent=2, ensure_ascii=False)
                    
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        
                elif format_type in ('rdata', 'rds'):
                    final_ext = ".RData" if format_type == "rdata" else ".rds"
                    final_path = os.path.join(target_dir, f"{dataset_name}{final_ext}")
                    delimiter_char = '\t' if ext == '.tsv' else ','
                    
                    if format_type == 'rdata':
                        r_command = "args <- commandArgs(trailingOnly=TRUE); df <- read.csv(args[1], sep=args[2], stringsAsFactors=FALSE); save(df, file=args[3])"
                    else:
                        r_command = "args <- commandArgs(trailingOnly=TRUE); df <- read.csv(args[1], sep=args[2], stringsAsFactors=FALSE); saveRDS(df, file=args[3])"
                        
                    result = subprocess.run(["Rscript", "-e", r_command, temp_file_path, delimiter_char, final_path], capture_output=True, text=True)
                    
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        
                    if result.returncode != 0:
                        raise Exception(f"Rscript Fehler: {result.stderr.strip()}")
                else:
                    raise Exception("Ungültiges Format ausgewählt.")
                
                self.send_success_response({
                    "message": "Erfolgreich heruntergeladen!",
                    "file_path": final_path
                })
            except Exception as e:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                self.send_error_response(str(e))
        elif self.path == '/install_pyarrow':
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', 'pyarrow'],
                    capture_output=True, text=True, timeout=120
                )
                check_parquet_available()
                if result.returncode == 0:
                    self.send_success_response({
                        "success": True,
                        "message": "pyarrow erfolgreich installiert.",
                        "parquet_available": PARQUET_AVAILABLE
                    })
                else:
                    self.send_error_response(result.stderr.strip() or "Installation fehlgeschlagen.")
            except subprocess.TimeoutExpired:
                self.send_error_response("Installation dauerte zu lange (> 120s).")
            except Exception as e:
                self.send_error_response(str(e))
        elif self.path == '/refresh_rdatasets':
            try:
                csv_path = RDATASETS_CSV
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                load_rdatasets()
                self.send_success_response({
                    "success": True,
                    "count": len(rdatasets_cache),
                    "cached_at": rdatasets_cached_at
                })
            except Exception as e:
                self.send_error_response(str(e))
        else:
            self.send_error_response("Nicht gefunden", code=404)

    def send_success_response(self, data):
        self.send_response(200)
        origin = self.headers.get('Origin', '')
        self.send_header('Access-Control-Allow-Origin', origin if origin else '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, message, code=400):
        self.send_response(code)
        origin = self.headers.get('Origin', '')
        self.send_header('Access-Control-Allow-Origin', origin if origin else '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    check_r_available()
    check_parquet_available()

    # Start blocking initialization in background
    def background_init():
        load_rdatasets()
        ensure_kaggle_venv()
    
    init_thread = threading.Thread(target=background_init, daemon=True)
    init_thread.start()

    def watchdog():
        while True:
            time.sleep(5)
            if time.time() - last_heartbeat > HEARTBEAT_TIMEOUT:
                print("Heartbeat expired — shutting down.")
                os._exit(0)

    threading.Thread(target=watchdog, daemon=True).start()

    port = 18700
    try:
        # Quick check if port is available without starting the server
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.bind(('127.0.0.1', port))
        s.close()
    except OSError:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()

    os.makedirs(CACHE_DIR, exist_ok=True)
    port_file = os.path.join(CACHE_DIR, 'port')
    with open(port_file, 'w') as f:
        f.write(str(port))
    pid_file = os.path.join(CACHE_DIR, 'server.pid')
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))

    server = ThreadPoolHTTPServer(('127.0.0.1', port), Handler, max_workers=10)
    print(f"Python server listening on 127.0.0.1:{port}")
    server.serve_forever()
