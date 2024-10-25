import requests
import os
import hashlib
import sys
import logging
import json
import argparse
import csv
from collections import Counter
from time import sleep

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Constants and Configuration
DMR_CSV_URL = "https://radioid.net/static/user.csv"
NORWAY_CSV_URL = "https://nkom.no/frekvenser-og-elektronisk-utstyr/radioamator/_/attachment/download/e7908c8f-ab3e-47b3-9e1e-8aa86e13664f:25cd0f93a2d15d065245df12e84a0bac95b6d2e9/Liste%20over%20norske%20radioamat%C3%B8rer%20(CSV).csv"
DMR_CSV_FILENAME = "user.csv"
NORWAY_CSV_FILENAME = "user-no.csv"
DMR_META_FILENAME = "user.meta"
NORWAY_META_FILENAME = "user-no.meta"
LINE_SEPARATOR = "-" * 75

class MetadataHandler:
    """Handles loading and saving metadata in JSON format."""
    def __init__(self, filename):
        self.filename = filename
        self.metadata = self.load_metadata()

    def load_metadata(self):
        """Load metadata from file or initialize with an empty dictionary."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as meta_file:
                    return json.load(meta_file)
            except json.JSONDecodeError:
                logger.error("Error decoding JSON metadata. File may be corrupted.")
        return {}

    def save_metadata(self):
        """Save metadata to file."""
        with open(self.filename, 'w') as meta_file:
            json.dump(self.metadata, meta_file, indent=4)
        logger.info(f"Metadata saved to {self.filename}.")

    def get(self, key, default=None):
        """Get a metadata value."""
        return self.metadata.get(key, default)

    def set(self, key, value):
        """Set a metadata value and save."""
        self.metadata[key] = value
        self.save_metadata()

def calculate_md5(file_path):
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"MD5 calculation failed for {file_path}: {e}")
        return None

def show_progress(downloaded, total_size, bar_length=50):
    """Displays a progress bar if total_size is known, otherwise shows bytes downloaded."""
    if total_size > 0:
        progress = downloaded / total_size
        bar = "#" * int(bar_length * progress) + "-" * (bar_length - int(bar_length * progress))
        sys.stdout.write(f"\r[{bar}] {progress * 100:.2f}% - {downloaded / (1024 * 1024):.2f} MB")
    else:
        sys.stdout.write(f"\rDownloaded {downloaded / (1024 * 1024):.2f} MB")
    sys.stdout.flush()

def download_csv(url, filename, metadata, max_retries=3):
    """Download the CSV file, checking Last-Modified and updating metadata."""
    logger.info(f"Starting download from {url}")
    headers = {}
    if metadata.get('Last-Modified'):
        headers['If-Modified-Since'] = metadata.get('Last-Modified')
    
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=10)
            if response.status_code == 304:
                print("File has not been modified since the last download.")
                return False  # No download needed
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.warning(f"Download error: {e}. Retrying ({retries}/{max_retries})...")
            sleep(2 ** retries)  # Exponential backoff

    if retries == max_retries:
        logger.error("Max retries reached. Download failed.")
        return False

    total_size = int(response.headers.get('content-length', 0)) if response.headers.get('content-length') else 0
    downloaded = 0
    with open(filename, "wb") as file:
        for data in response.iter_content(1024):
            downloaded += len(data)
            file.write(data)
            show_progress(downloaded, total_size)
    print("\nDownload completed.")
    
    # Update metadata with new Last-Modified and MD5
    metadata.set('Last-Modified', response.headers.get("Last-Modified"))
    metadata.set('MD5', calculate_md5(filename))
    return True

def count_entries(filename, metadata, country_column='COUNTRY'):
    """Count entries in the CSV file and calculate contact statistics."""
    try:
        with open(filename, "r", encoding='latin-1') as file:  # Use 'latin-1' encoding for Norwegian file
            reader = csv.DictReader(file, delimiter=';' if 'user-no.csv' in filename else ',')
            country_counts = Counter(row[country_column] for row in reader if country_column in row and row[country_column])
            
            # Update metadata with counts
            total_contacts = sum(country_counts.values())
            metadata.set('Total Contacts', total_contacts)
            metadata.set('Contacts Per Country', dict(country_counts))
            
            logger.info("Contact statistics updated in metadata.")
            return total_contacts
    except FileNotFoundError:
        logger.error(f"File not found: {filename}")
        return 0
    except Exception as e:
        logger.error(f"Error counting entries: {e}")
        return 0

def main(force_download=False):
    # Download and process DMR database
    dmr_metadata = MetadataHandler(DMR_META_FILENAME)
    if force_download or download_csv(DMR_CSV_URL, DMR_CSV_FILENAME, dmr_metadata):
        entries = count_entries(DMR_CSV_FILENAME, dmr_metadata)
        print(f"Number of DMR entries: {entries}")
    else:
        print("No updates found for DMR database.")
    
    # Download and process Norwegian contacts
    norway_metadata = MetadataHandler(NORWAY_META_FILENAME)
    if force_download or download_csv(NORWAY_CSV_URL, NORWAY_CSV_FILENAME, norway_metadata):
        entries = count_entries(NORWAY_CSV_FILENAME, norway_metadata, country_column='Land')
        print(f"Number of Norwegian entries: {entries}")
    else:
        print("No updates found for Norwegian contacts.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and manage DMR and Norwegian radio amateur databases.")
    parser.add_argument('-f', '--force', action='store_true', help="Force download even if file is up-to-date")
    args = parser.parse_args()

    main(force_download=args.force)

