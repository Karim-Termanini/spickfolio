import os
import threading
import urllib.request

from stats_sheets import config
from stats_sheets.security import validate_url


def get_url_size(url):
    ok, _ = validate_url(url)
    if not ok:
        return None
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            content_length = response.getheader('Content-Length')
            if content_length:
                return int(content_length)
    except Exception as e:
        print(f"HEAD size check failed for {url}: {e}")
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
    if not config.PARQUET_AVAILABLE:
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
