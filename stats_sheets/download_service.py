import csv
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request

from stats_sheets import config
from stats_sheets.data_helpers import download_http_to_file, parquet_to_csv
from stats_sheets.download_jobs import DownloadCancelled, is_job_cancelled, update_job
from stats_sheets.security import has_invalid_download_path_chars, is_denied_download_dir, validate_url


def validate_download_request(data):
    url = data.get('url')
    dataset_name = data.get('dataset_name', 'dataset').strip()
    format_type = data.get('format', 'csv').strip().lower()
    target_dir = data.get('target_dir', '').strip()

    if format_type in ('rdata', 'rds') and not config.R_AVAILABLE:
        return None, 'R ist auf dem Server nicht verfügbar. RData/RDS-Export ist deaktiviert.'
    if not url:
        return None, 'URL-Parameter fehlt.'
    if not url.startswith('kaggle:'):
        ok, err = validate_url(url)
        if not ok:
            return None, err

    safe_name = re.sub(r'[^\w\s.-]', '', dataset_name).strip() or 'dataset'

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
        return None, 'Zielordner muss ein absoluter Pfad sein.'
    if has_invalid_download_path_chars(target_dir):
        return None, 'Zielordner enthält ungültige Zeichen.'
    if is_denied_download_dir(target_dir):
        return None, 'Dieses Verzeichnis ist als Ziel nicht erlaubt.'
    if not os.path.isdir(target_dir):
        return None, 'Zielordner existiert nicht.'
    if not os.access(target_dir, os.W_OK | os.X_OK):
        return None, 'Keine Schreibrechte für den Zielordner.'

    return {
        'url': url,
        'dataset_name': safe_name,
        'format_type': format_type,
        'target_dir': target_dir,
    }, None


def _set_download_progress(job_id, bytes_read, bytes_total=None):
    update_job(job_id, phase='downloading', bytes_read=bytes_read, bytes_total=bytes_total)


def _set_converting(job_id):
    _check_cancelled(job_id)
    update_job(job_id, phase='converting', bytes_read=0, bytes_total=None)


def _check_cancelled(job_id):
    if is_job_cancelled(job_id):
        raise DownloadCancelled()


def _run_kaggle_download(job_id, dataset_ref, download_dir):
    proc = subprocess.Popen(
        [config.VENV_KAGGLE, 'datasets', 'download', '-d', dataset_ref, '-p', download_dir, '--unzip'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        while proc.poll() is None:
            if is_job_cancelled(job_id):
                proc.kill()
                proc.wait()
                shutil.rmtree(download_dir, ignore_errors=True)
                raise DownloadCancelled()
            time.sleep(0.25)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            shutil.rmtree(download_dir, ignore_errors=True)
            raise Exception(f'Kaggle Download Fehler: {stderr.strip()} {stdout.strip()}')
        _check_cancelled(job_id)
    except DownloadCancelled:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        shutil.rmtree(download_dir, ignore_errors=True)
        raise


def run_download_job(job_id, payload):
    url = payload['url']
    dataset_name = payload['dataset_name']
    format_type = payload['format_type']
    target_dir = payload['target_dir']

    ext = '.csv'
    lower_url = url.lower()
    if lower_url.endswith('.json'):
        ext = '.json'
    elif lower_url.endswith('.tsv'):
        ext = '.tsv'
    elif lower_url.endswith('.parquet'):
        ext = '.parquet'

    temp_file_path = os.path.join(target_dir, f'temp_{dataset_name}{ext}')
    update_job(job_id, phase='downloading', bytes_read=0, bytes_total=None)

    try:
        os.makedirs(target_dir, exist_ok=True)
        _check_cancelled(job_id)

        if url.startswith('kaggle:'):
            dataset_ref = url.split('kaggle:')[1]
            download_dir = os.path.join(target_dir, f'kaggle_temp_{dataset_name}')
            os.makedirs(download_dir, exist_ok=True)
            update_job(job_id, phase='downloading', bytes_read=0, bytes_total=None)

            _run_kaggle_download(job_id, dataset_ref, download_dir)

            all_files = []
            for root, _dirs, files in os.walk(download_dir):
                for file in files:
                    all_files.append(os.path.join(root, file))

            if not all_files:
                shutil.rmtree(download_dir, ignore_errors=True)
                raise Exception('Kaggle-Datensatz enthält keine Dateien.')

            if len(all_files) == 1:
                shutil.move(all_files[0], temp_file_path)
                shutil.rmtree(download_dir, ignore_errors=True)
                if all_files[0].lower().endswith('.csv'):
                    ext = '.csv'
            else:
                dataset_dir = os.path.join(target_dir, dataset_name)
                os.makedirs(dataset_dir, exist_ok=True)
                for f in all_files:
                    rel = os.path.relpath(f, download_dir)
                    dst = os.path.join(dataset_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(f, dst)
                shutil.rmtree(download_dir, ignore_errors=True)
                update_job(
                    job_id,
                    phase='done',
                    done=True,
                    file_path=dataset_dir,
                    path_is_dir=True,
                    message=f'Dataset heruntergeladen ({len(all_files)} Dateien in {dataset_name}/)',
                )
                return
        else:
            def on_progress(read, total):
                _check_cancelled(job_id)
                _set_download_progress(job_id, read, total)

            download_http_to_file(
                url,
                temp_file_path,
                on_progress=on_progress,
                should_cancel=lambda: is_job_cancelled(job_id),
            )

        _set_converting(job_id)
        final_path = _convert_and_finalize(temp_file_path, target_dir, dataset_name, format_type, ext)

        update_job(
            job_id,
            phase='done',
            done=True,
            file_path=final_path,
            path_is_dir=os.path.isdir(final_path),
            message='Erfolgreich heruntergeladen!',
            bytes_read=0,
            bytes_total=None,
        )
    except Exception:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise


def _convert_and_finalize(temp_file_path, target_dir, dataset_name, format_type, ext):
    if ext == '.parquet':
        if format_type == 'csv':
            final_path = os.path.join(target_dir, f'{dataset_name}.csv')
            if not parquet_to_csv(temp_file_path, final_path):
                raise Exception('Parquet-Konvertierung fehlgeschlagen.')
            os.remove(temp_file_path)
            return final_path
        if format_type == 'json':
            csv_tmp = temp_file_path + '_conv.csv'
            final_path = os.path.join(target_dir, f'{dataset_name}.json')
            if not parquet_to_csv(temp_file_path, csv_tmp):
                raise Exception('Parquet-Konvertierung fehlgeschlagen.')
            rows = []
            with open(csv_tmp, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
            os.remove(csv_tmp)
            with open(final_path, mode='w', encoding='utf-8') as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)
            os.remove(temp_file_path)
            return final_path
        if format_type in ('rdata', 'rds'):
            csv_tmp = temp_file_path + '_conv.csv'
            final_ext = '.RData' if format_type == 'rdata' else '.rds'
            final_path = os.path.join(target_dir, f'{dataset_name}{final_ext}')
            if not parquet_to_csv(temp_file_path, csv_tmp):
                raise Exception('Parquet-Konvertierung fehlgeschlagen.')
            os.remove(temp_file_path)
            r_command = (
                'args <- commandArgs(trailingOnly=TRUE); '
                'df <- read.csv(args[1], stringsAsFactors=FALSE); '
                f"{'save(df, file=args[2])' if format_type == 'rdata' else 'saveRDS(df, file=args[2])'}"
            )
            result = subprocess.run(
                ['Rscript', '-e', r_command, csv_tmp, final_path],
                capture_output=True,
                text=True,
            )
            os.remove(csv_tmp)
            if result.returncode != 0:
                raise Exception(f'Rscript Fehler: {result.stderr.strip()}')
            return final_path
        raise Exception('Ungültiges Format ausgewählt.')

    if format_type == 'csv':
        final_path = os.path.join(target_dir, f'{dataset_name}.csv')
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(temp_file_path, final_path)
        return final_path

    if format_type == 'json':
        final_path = os.path.join(target_dir, f'{dataset_name}.json')
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
        return final_path

    if format_type in ('rdata', 'rds'):
        final_ext = '.RData' if format_type == 'rdata' else '.rds'
        final_path = os.path.join(target_dir, f'{dataset_name}{final_ext}')
        delimiter_char = '\t' if ext == '.tsv' else ','
        if format_type == 'rdata':
            r_command = 'args <- commandArgs(trailingOnly=TRUE); df <- read.csv(args[1], sep=args[2], stringsAsFactors=FALSE); save(df, file=args[3])'
        else:
            r_command = 'args <- commandArgs(trailingOnly=TRUE); df <- read.csv(args[1], sep=args[2], stringsAsFactors=FALSE); saveRDS(df, file=args[3])'
        result = subprocess.run(
            ['Rscript', '-e', r_command, temp_file_path, delimiter_char, final_path],
            capture_output=True,
            text=True,
        )
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if result.returncode != 0:
            raise Exception(f'Rscript Fehler: {result.stderr.strip()}')
        return final_path

    raise Exception('Ungültiges Format ausgewählt.')
