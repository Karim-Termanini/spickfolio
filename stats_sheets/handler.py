import csv
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from stats_sheets import config
from stats_sheets.capabilities import check_parquet_available, ensure_kaggle_credentials_dir, kaggle_auth_configured
from stats_sheets.hf_cache import get_hf_datasets
from stats_sheets.data_helpers import (
    get_url_size,
    parquet_to_csv,
    preview_parquet_url,
    trim_truncated,
)
from stats_sheets.rdatasets_loader import load_rdatasets
from stats_sheets.rate_limit import is_rate_limited, seconds_until_allowed
from stats_sheets.download_jobs import create_job, get_job, request_cancel, start_download_job
from stats_sheets.download_service import run_download_job, validate_download_request
from stats_sheets.desktop_actions import open_path_in_file_manager, open_path_on_desktop, send_desktop_notification
from stats_sheets.kaggle_helpers import kaggle_preview_blocked, kaggle_previewable
from stats_sheets.security import validate_url
from stats_sheets.static_files import CONTENT_TYPES, STATIC_ROUTES, resolve_static_path

ALLOWED_ORIGINS = config.ALLOWED_ORIGINS

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
        if parsed_path.path not in ('/heartbeat', '/config', '/download/status') and is_rate_limited(self.client_address[0]):
            retry_after = seconds_until_allowed(self.client_address[0])
            self.send_error_response("Too many requests", code=429, retry_after=retry_after)
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
            if source in ('all', 'rdatasets') and config.rdatasets_cache:
                for row in config.rdatasets_cache:
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
                    hf_data, _hf_cached = get_hf_datasets(query)
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
                if not kaggle_auth_configured():
                    kaggle_skipped = True
                    if source == 'kaggle':
                        self.send_success_response({"needs_auth": True})
                        return
                else:
                    try:
                        env = os.environ.copy()
                        kaggle_cmd = [config.VENV_KAGGLE, 'datasets', 'list', '--csv']
                        if query:
                            kaggle_cmd = [config.VENV_KAGGLE, 'datasets', 'list', '-s', query, '--csv']
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
                if r.get('source') == 'kaggle':
                    r['previewable'] = kaggle_previewable(r.get('size', ''))
                else:
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

            if not data_files and api_parquet and not config.PARQUET_AVAILABLE:
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
            ok, url_err = validate_url(url)
            if not ok:
                self.send_error_response(error_code=url_err)
                return
            size = get_url_size(url)
            self.send_success_response({"size": size})
        elif parsed_path.path == '/preview':
            url = params.get('url', [''])[0].strip()
            if not url:
                self.send_error_response("url parameter is required")
                return
            if not url.startswith('kaggle:'):
                ok, url_err = validate_url(url)
                if not ok:
                    self.send_error_response(error_code=url_err)
                    return
            if url.startswith('kaggle:'):
                size_param = params.get('size', [''])[0].strip()
                if kaggle_preview_blocked(size_param):
                    self.send_success_response({"error_code": "kaggle_preview_too_large"})
                    return
                try:
                    dataset_ref = url.split('kaggle:')[1]
                    tmpdir = os.path.join('/tmp', f'kaggle_preview_{threading.get_ident()}')
                    if os.path.exists(tmpdir):
                        shutil.rmtree(tmpdir)
                    os.makedirs(tmpdir, exist_ok=True)

                    result = subprocess.run([config.VENV_KAGGLE, 'datasets', 'download', '-d', dataset_ref, '-p', tmpdir, '--unzip'], capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        shutil.rmtree(tmpdir, ignore_errors=True)
                        err = (result.stderr.strip() or result.stdout.strip())
                        if '403' in err:
                            self.send_success_response({"error_code": "kaggle_preview_forbidden"})
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
                    self.send_success_response({"error_code": "kaggle_preview_timeout"})
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
            file_path = os.path.join(config.BASE_DIR, f'{lang}.json')
            if not os.path.exists(file_path):
                self.send_error_response(f"Translations for '{lang}' not found")
                return
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.send_success_response(json.load(f))
            except Exception as e:
                self.send_error_response(str(e))
        elif parsed_path.path == '/cheat-sheet':
            file_path = os.path.join(config.BASE_DIR, 'cheat-sheet-data.json')
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
                "r_available": config.R_AVAILABLE,
                "parquet_available": config.PARQUET_AVAILABLE,
                "kaggle_auth": kaggle_auth_configured(),
                "downloads_dir": get_xdg_dir('DOWNLOAD', '~/Downloads'),
                "documents_dir": get_xdg_dir('DOCUMENTS', '~/Documents'),
                "rdatasets_cached_at": config.rdatasets_cached_at,
            })
        elif parsed_path.path == '/download/status':
            job_id = params.get('job_id', [''])[0].strip()
            if not job_id:
                self.send_error_response(error_code='download_job_id_missing')
                return
            job = get_job(job_id)
            if not job:
                self.send_error_response(code=404, error_code='download_job_not_found')
                return
            self.send_success_response(job)
        elif parsed_path.path == '/heartbeat':
            config.last_heartbeat = time.time()
            self.send_success_response({"ok": True})
        else:
            self.send_error_response("Endpoint nicht gefunden", code=404)

    def do_POST(self):
        if not self._check_origin():
            return
        if is_rate_limited(self.client_address[0]):
            retry_after = seconds_until_allowed(self.client_address[0])
            self.send_error_response("Too many requests", code=429, retry_after=retry_after)
            return
        if self.path == '/download':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            payload, err_code = validate_download_request(data)
            if err_code:
                self.send_error_response(error_code=err_code)
                return

            job_id = create_job()
            start_download_job(job_id, payload, run_download_job)
            self.send_success_response({"job_id": job_id})
        elif self.path == '/download/cancel':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            job_id = data.get('job_id', '').strip()
            if not job_id:
                self.send_error_response("job_id fehlt.")
                return
            if not request_cancel(job_id):
                self.send_error_response("Download-Job nicht gefunden oder bereits beendet.", code=404)
                return
            self.send_success_response({"ok": True})
        elif self.path == '/open_path':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            path = data.get('path', '').strip()
            action = data.get('action', 'folder').strip().lower()
            if action not in ('folder', 'file'):
                self.send_error_response("Ungültige action.")
                return
            ok, err_code = open_path_on_desktop(path, action=action)
            if not ok:
                self.send_error_response(error_code=err_code)
                return
            self.send_success_response({"ok": True})
        elif self.path == '/notify':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            title = data.get('title', '').strip()
            body = data.get('body', '').strip()
            ok, err = send_desktop_notification(title, body)
            if not ok:
                self.send_error_response(err)
                return
            self.send_success_response({"ok": True})
        elif self.path == '/kaggle/open_credentials_dir':
            path = ensure_kaggle_credentials_dir()
            ok, err_code = open_path_in_file_manager(path)
            if not ok:
                self.send_error_response(error_code=err_code)
                return
            self.send_success_response({"ok": True, "path": path})
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
                        "parquet_available": config.PARQUET_AVAILABLE
                    })
                else:
                    self.send_error_response(result.stderr.strip() or "Installation fehlgeschlagen.")
            except subprocess.TimeoutExpired:
                self.send_error_response("Installation dauerte zu lange (> 120s).")
            except Exception as e:
                self.send_error_response(str(e))
        elif self.path == '/refresh_rdatasets':
            try:
                csv_path = config.RDATASETS_CSV
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                load_rdatasets()
                self.send_success_response({
                    "success": True,
                    "count": len(config.rdatasets_cache),
                    "cached_at": config.rdatasets_cached_at
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

    def send_error_response(self, message=None, code=400, error_code=None, retry_after=None):
        self.send_response(code)
        origin = self.headers.get('Origin', '')
        self.send_header('Access-Control-Allow-Origin', origin if origin else '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        if retry_after is not None:
            self.send_header('Retry-After', str(retry_after))
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        body = {}
        if error_code:
            body['error_code'] = error_code
        if message:
            body['error'] = message
        self.wfile.write(json.dumps(body).encode('utf-8'))

    def log_message(self, format, *args):
        pass

