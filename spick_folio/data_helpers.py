import os
import threading
import urllib.request

from spick_folio import config
from spick_folio.api_errors import DownloadError
from spick_folio.security import SsrfBlockedError, safe_urlopen, validate_url


def get_url_size(url):
    ok, _ = validate_url(url)
    if not ok:
        return None
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        with safe_urlopen(req, timeout=5) as response:
            content_length = response.getheader('Content-Length')
            if content_length:
                return int(content_length)
    except SsrfBlockedError:
        raise
    except Exception as e:
        print(f"HEAD size check failed for {url}: {e}")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Range': 'bytes=0-0'
        })
        with safe_urlopen(req, timeout=5) as response:
            content_range = response.getheader('Content-Range')
            if content_range:
                total = content_range.split('/')[-1]
                if total.isdigit():
                    return int(total)
            content_length = response.getheader('Content-Length')
            if content_length:
                return int(content_length)
    except SsrfBlockedError:
        raise
    except Exception as e:
        print(f"Range size check failed for {url}: {e}")
    try:
        req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'Mozilla/5.0'})
        with safe_urlopen(req, timeout=5) as response:
            content_length = response.getheader('Content-Length')
            if content_length:
                return int(content_length)
    except SsrfBlockedError:
        raise
    except Exception as e:
        print(f"GET size check failed for {url}: {e}")
    return None


def download_http_to_file(url, dest_path, on_progress=None, should_cancel=None, chunk_size=65536):
    from spick_folio.download_jobs import DownloadCancelled

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response_ctx = safe_urlopen(req)
    except SsrfBlockedError as exc:
        raise DownloadError(exc.error_code) from exc
    with response_ctx as response:
        total_header = response.getheader('Content-Length')
        total = int(total_header) if total_header and str(total_header).isdigit() else None
        if on_progress:
            on_progress(0, total)
        read = 0
        with open(dest_path, 'wb') as out_file:
            while True:
                if should_cancel and should_cancel():
                    raise DownloadCancelled()
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                read += len(chunk)
                if on_progress:
                    on_progress(read, total)
    return read


class ParquetPreviewTooLarge(Exception):
    """Raised when a Parquet preview download exceeds the configured byte cap."""


def _download_bounded(url, dest_path, max_bytes, chunk_size=None):
    chunk_size = chunk_size or config.PARQUET_PREVIEW_CHUNK_SIZE
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with safe_urlopen(req, timeout=30) as response:
        content_length = response.getheader('Content-Length')
        if content_length and str(content_length).isdigit():
            if int(content_length) > max_bytes:
                raise ParquetPreviewTooLarge()
        read = 0
        with open(dest_path, 'wb') as out_file:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                read += len(chunk)
                if read > max_bytes:
                    raise ParquetPreviewTooLarge()
                out_file.write(chunk)


def _cell_to_preview_value(val):
    if hasattr(val, '__len__') and not isinstance(val, (str, bytes)):
        return str(val)
    return val


def _rows_from_arrow_table(table, max_rows):
    columns = table.column_names
    rows = []
    for i in range(min(max_rows, table.num_rows)):
        row = {}
        for col in columns:
            row[col] = _cell_to_preview_value(table.column(col)[i].as_py())
        rows.append(row)
    return columns, rows


def _read_parquet_preview_rows(path, max_rows=10):
    try:
        import pyarrow.parquet as pq
        parquet_file = pq.ParquetFile(path)
        if parquet_file.num_row_groups == 0:
            return [], []
        first_group = parquet_file.read_row_group(0)
        table = first_group.slice(0, min(max_rows, first_group.num_rows))
        return _rows_from_arrow_table(table, max_rows)
    except ImportError:
        import pandas as pd
        df = pd.read_parquet(path)
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
        return columns, rows


def preview_parquet_url(url, max_rows=10):
    if not config.PARQUET_AVAILABLE:
        return None, "Parquet preview is not available — install pyarrow or pandas"
    ok, _ = validate_url(url)
    if not ok:
        return None, "Ungültige URL."
    tmp = None
    try:
        known_size = get_url_size(url)
        if known_size is not None and known_size > config.PARQUET_PREVIEW_MAX_BYTES:
            return None, 'parquet_preview_too_large'

        tmp = os.path.join('/tmp', f'parquet_preview_{threading.get_ident()}.parquet')
        _download_bounded(url, tmp, config.PARQUET_PREVIEW_MAX_BYTES)
        columns, rows = _read_parquet_preview_rows(tmp, max_rows=max_rows)
        return {"columns": columns, "rows": rows}, None
    except ParquetPreviewTooLarge:
        return None, 'parquet_preview_too_large'
    except SsrfBlockedError:
        raise
    except Exception as e:
        return None, str(e)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def parquet_to_csv(parquet_path, csv_path):
    if not config.PARQUET_AVAILABLE:
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
    try:
        raw = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raw = raw_bytes.decode('utf-8', errors='replace')
        if raw and raw[-1] == '\ufffd':
            raw = raw[:-1]
    last_nl = raw.rfind('\n')
    if last_nl >= 0:
        raw = raw[:last_nl]
    return raw
