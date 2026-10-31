"""Downloads and unpacks the FCC amateur radio data."""

import os
import shutil
import time
import zipfile
from pathlib import Path

import requests

from .config import DownloadConfig


def clean_temp_files(zip_path: Path, unpacked_dir: Path) -> None:
    """Remove the zip file and unpacked folder left over from a previous run.

    On Windows (notably under OneDrive) the folder can stay locked after its
    contents are deleted. The removal is retried, and an empty leftover folder
    is tolerated because unpacking reuses it.

    Raises:
        PermissionError: Files are still left in the folder after all retries.
    """
    if unpacked_dir.is_dir():
        for attempt in range(1, 4):
            try:
                shutil.rmtree(unpacked_dir)
                break
            except PermissionError:
                if attempt < 3:
                    time.sleep(2)
                    continue
                shutil.rmtree(unpacked_dir, ignore_errors=True)
                if any(unpacked_dir.rglob('*')):
                    raise
                print(f'Could not remove empty folder "{unpacked_dir}"; reusing it.')
    if zip_path.is_file():
        os.remove(zip_path)


def download_zip(url: str, zip_path: Path, settings: DownloadConfig) -> None:
    """Download the raw .zip file from the FCC.

    Args:
        url: Location of the FCC ``l_amat.zip`` file.
        zip_path: Where to save it. Parent folders are created.
        settings: Retry count and timeouts.

    Raises:
        RuntimeError: The download failed or timed out on every attempt.
    """
    print(f'Starting file download from: {url}')
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    timeout = (settings.connect_timeout, settings.read_timeout)

    for attempt in range(1, settings.max_retries + 1):
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f'Compressed FCC database files downloaded to "{zip_path}"\n')
            return
        except requests.exceptions.Timeout:
            print(f'Download timed out (attempt {attempt}/{settings.max_retries})')
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f'Error downloading file: {e}') from e

    raise RuntimeError('Max retries reached. Download failed.')


def unpack_zip(zip_path: Path, unpacked_dir: Path) -> None:
    """Extract the downloaded zip so the .DAT files can be read.

    Raises:
        RuntimeError: The file is missing or is not a valid zip archive.
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            unpacked_dir.mkdir(parents=True, exist_ok=True)
            zip_ref.extractall(unpacked_dir)
    except zipfile.BadZipFile as e:
        raise RuntimeError(f'{zip_path} is not a valid zip file') from e
    except FileNotFoundError as e:
        raise RuntimeError(f'Zip file not found at {zip_path}') from e
    print(f'{zip_path} extracted to "{unpacked_dir}"\n')
