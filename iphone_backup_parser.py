import argparse
import logging
import math
import os
import plistlib
import re
import shutil
import sqlite3
import subprocess
import time

import magic

# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

def is_sqlite3(_path):
    """
    Check if a file is an SQLite3 database by calling 'file <filename>'.
    If 'sqlite' is in the output, return True.
    """
    try:
        process = subprocess.run(
            ['file', _path],
            check=True,
            stdout=subprocess.PIPE,
            universal_newlines=True
        )
        output = f'{process.stdout}'.lower()
        return 'sqlite' in output
    except subprocess.CalledProcessError as e:
        logging.error(f'[x] Unable to determine file type for: {_path} -> {e}')
        return False

def parse_args():
    """
    Parse command-line arguments using argparse. 
    User must provide the path to the target SQLite3 manifest file.
    """
    parser = argparse.ArgumentParser(
        description='Parse iPhone backup manifest.db for links, images, and more.'
    )
    parser.add_argument(
        'file_path',
        help='Target SQLite3 Path (manifest.db)',
        type=str
    )
    return parser.parse_args()

def print_elapsed_time(start_time):
    """
    Log the total elapsed time in MM:SS format.
    """
    seconds = time.time() - start_time
    minutes = math.floor(seconds / 60)
    remaining_seconds = int(seconds - (minutes * 60))
    elapsed_time = f'{minutes:02d}:{remaining_seconds:02d}'
    logging.info(f'[i] Total Time Elapsed: {elapsed_time}')

def convert_sqlite3_to_sql_dict(sqlite_path):
    """
    Read all tables from the SQLite database and store each row in 
    a dictionary: { "<tableName>_<rowID>": row_contents, ... }
    """
    result_dict = {}
    try:
        with sqlite3.connect(sqlite_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
            tables = cursor.fetchall()
            for table in tables:
                table_name = table[0]
                qry = f'SELECT * FROM "{table_name}"'
                cursor.execute(qry)
                contents = cursor.fetchall()
                for content in contents:
                    uuid = content[0]
                    key = f'{table_name}_{uuid}'
                    result_dict[key] = content
    except sqlite3.Error as e:
        logging.error(f'[x] SQLite Error while reading: {sqlite_path} -> {e}')
    return result_dict

def re_extract_urls(url_string_or_bytes, url_block_list, add_url_func):
    """
    Extract any URLs from a string or bytes object. 
    The add_url_func is a callback used to add a URL to a set (or other structure).
    """
    if isinstance(url_string_or_bytes, bytes):
        try:
            url_string_or_bytes = url_string_or_bytes.decode('ascii', 'ignore')
        except UnicodeDecodeError as e:
            logging.warning(f'[!] Could not decode bytes -> {e}')
            return

    # If it's still not a string by here, bail out
    if not isinstance(url_string_or_bytes, str):
        return

    url_list = re.findall(r'(https?://\S+)', url_string_or_bytes)
    for url in url_list:
        # Check blocklist inside add_url_func
        add_url_func(url, url_block_list)

def global_filter(obj, url_block_list, add_url_func):
    """
    Recursively parse Python structures (dict, list, set, etc.), searching for URLs,
    and also parse embedded binary plists if found.
    """
    if isinstance(obj, (int, str)):
        # Extract any URLs from string or int (int -> str)
        re_extract_urls(str(obj), url_block_list, add_url_func)
        return obj
    elif isinstance(obj, bytes):
        # If it looks like a plist, try to parse it
        try:
            obj_str = obj.decode('ascii', 'ignore')
            if 'bplist' in obj_str:
                # Attempt to parse as plist
                try:
                    loaded_plist = plistlib.loads(obj, fmt=None, dict_type=dict)
                    global_filter(loaded_plist, url_block_list, add_url_func)
                except Exception as e:
                    logging.warning(f'[!] Unable to parse as bplist -> {e}')
            re_extract_urls(obj, url_block_list, add_url_func)
        except Exception as e:
            logging.warning(f'[!] Exception decoding bytes -> {e}')
        return obj
    elif isinstance(obj, dict):
        # Re-extract any URLs in keys and values
        for k, v in list(obj.items()):
            re_extract_urls(str(k), url_block_list, add_url_func)
            obj[k] = global_filter(v, url_block_list, add_url_func)
        return obj
    elif isinstance(obj, (list, tuple)):
        # Re-extract any URLs from each item
        new_list = []
        for item in obj:
            new_list.append(global_filter(item, url_block_list, add_url_func))
        return new_list
    elif isinstance(obj, set):
        new_set = set()
        for item in obj:
            new_set.add(global_filter(item, url_block_list, add_url_func))
        return new_set
    else:
        return obj

def generate_cleaned_manifest_entry(data_body):
    """
    Convert a row from the sqlite3 content into a structured dict.
    The original code had indexes for domain, sql_entry, etc.
    """
    serial = data_body[0]
    domain_data = data_body[1]
    sql_entry = data_body[2]
    unknown_number = data_body[3]
    manifest_data = data_body[4]

    entry_dict = {
        'serial': serial,
        'domain': domain_data,
        'sql_entry': sql_entry,
        'unknown_number': unknown_number,
        'manifest_data': manifest_data,
        'path': 'Unknown',
        'type': 'Unknown'
    }
    return entry_dict

def add_url(url, url_block_list, url_set=None):
    """
    Add URL to a set if it does not contain any blocklisted items.
    """
    if url_set is None:
        return
    for blocked_url in url_block_list:
        if blocked_url in url:
            return
    url_set.add(url)

def iterate_sql_dict(sql_dict, output_database, sms_database, url_block_list, url_set):
    """
    For each entry in the dictionary from the SQLite DB:
      1. Generate a cleaned manifest entry.
      2. Identify 'sms.db' references if present.
      3. Optionally process data for embedded URLs, etc.
    """
    sms_db_hash = None
    for key, data_body in sql_dict.items():
        try:
            # Convert to a structured dictionary
            manifest_entry = generate_cleaned_manifest_entry(data_body)
            output_database[manifest_entry['serial']] = manifest_entry

            # Identify 'sms.db'
            if 'sms.db' in manifest_entry['sql_entry']:
                sms_db_hash = manifest_entry['serial']

            # Perform a quick global_filter on the data body 
            # (some rows might contain text or plist data)
            global_filter(data_body, url_block_list, 
                          lambda u, block_list: add_url(u, block_list, url_set))

        except Exception as e:
            logging.error(f'[x] Error iterating {key} -> {e}')
    return sms_db_hash

def walk_the_backup(file_path):
    """
    Walk the directory containing the manifest.db file to build a dict:
    { <filename>: <full_path>, ... }
    """
    file_walk_database = {}
    target_path = os.path.dirname(file_path)
    for root, dirs, files in os.walk(target_path, topdown=False):
        for filename in files:
            full_path = os.path.join(root, filename)
            file_walk_database[filename] = full_path
    return file_walk_database

def add_metadata_to_db_file(output_database, file_walk_database, magic_generator):
    """
    For each entry in output_database, if the serial (key) is found in the file_walk_database,
    add the local path and the identified MIME type from 'magic'.
    """
    sha1_file_set = set(file_walk_database.keys())
    for key, val_dict in output_database.items():
        if key in sha1_file_set:
            location = file_walk_database[key]
            try:
                file_type = magic_generator.id_filename(location)
            except Exception as e:
                logging.warning(f'[!] Could not get MIME type for {location} -> {e}')
                file_type = 'Unknown'
            val_dict['path'] = location
            val_dict['type'] = file_type

def filter_manifest_by_domain_str(output_database, domain_str, print_report=False):
    """
    Return a dict of entries whose 'domain' matches domain_str exactly.
    If print_report is True, logs them out.
    """
    result_dict = {}
    type_dict = {}
    for key, val_dict in output_database.items():
        if val_dict['path'] != 'Unknown' and val_dict['domain'] == domain_str:
            result_dict[key] = val_dict
            t = val_dict['type']
            type_dict[t] = type_dict.get(t, 0) + 1
            if print_report:
                logging.info(f'[i] Key: {key} -> {val_dict}')

    if print_report:
        logging.info('[i] Type counts in this domain filter:')
        for t, count in type_dict.items():
            logging.info(f'[i] MIME Type: {t}  Count: {count}')

    return result_dict

def filter_manifest_by_mime_type(output_database, mime_substring, print_report=False):
    """
    Return a dict of entries whose 'type' (MIME) contains mime_substring.
    If print_report is True, logs them out.
    """
    result_dict = {}
    type_dict = {}
    for key, val_dict in output_database.items():
        if val_dict['path'] != 'Unknown' and mime_substring in val_dict['type']:
            result_dict[key] = val_dict
            t = val_dict['type']
            type_dict[t] = type_dict.get(t, 0) + 1
            if print_report:
                logging.info(f'[i] Key: {key} -> {val_dict}')

    if print_report:
        logging.info('[i] Type counts in this MIME filter:')
        for t, count in type_dict.items():
            logging.info(f'[i] MIME Type: {t}  Count: {count}')

    return result_dict

def filter_manifest_by_sql_entry(output_database, sql_substring, print_report=False):
    """
    Return a dict of entries whose 'sql_entry' contains sql_substring.
    If print_report is True, logs them out.
    """
    result_dict = {}
    type_dict = {}
    for key, val_dict in output_database.items():
        if val_dict['path'] != 'Unknown' and sql_substring in val_dict['sql_entry']:
            result_dict[key] = val_dict
            t = val_dict['type']
            type_dict[t] = type_dict.get(t, 0) + 1
            if print_report:
                logging.info(f'[i] Key: {key} -> {val_dict}')

    if print_report:
        logging.info('[i] Type counts in this sql_entry filter:')
        for t, count in type_dict.items():
            logging.info(f'[i] MIME Type: {t}  Count: {count}')

    return result_dict

def copy_to_tmp(data_dict):
    """
    Copy all files from the data_dict (which is an output_database) into 
    a timestamped output folder within the current working directory.
    """
    target_path = time.strftime("%Y%m%d-%H%M%S") + "_output"
    try:
        os.mkdir(target_path)
    except FileExistsError:
        logging.warning(f'[!] Output folder already exists: {target_path}')

    for key, val_dict in data_dict.items():
        filename = os.path.basename(val_dict['sql_entry']).replace(' ', '_')
        file_path = val_dict['path']
        if not os.path.isfile(file_path):
            logging.warning(f'[!] Source not found or not a file: {file_path}')
            continue
        dest_path = os.path.join(target_path, filename)
        try:
            shutil.copy(file_path, dest_path)
            logging.info(f'[i] Copied {file_path} -> {dest_path}')
        except Exception as e:
            logging.error(f'[x] Could not copy {file_path} -> {dest_path} : {e}')

def process_url_file(url_set):
    """
    Write all collected URLs to urls.txt, and log how many were found.
    """
    if not url_set:
        logging.info('[i] No URLs found, skipping write to urls.txt')
        return
    try:
        with open('urls.txt', 'w') as f_out:
            for url in url_set:
                f_out.write(f'{url}\n')
        logging.info(f'[i] Wrote {len(url_set)} URLs to urls.txt')
    except Exception as e:
        logging.error(f'[x] Error writing urls.txt -> {e}')

def examine_and_process_db_file(file_path, 
                                url_block_list, 
                                url_set,
                                output_database,
                                sms_database):
    """
    Main function that:
      1. Checks if file_path is an SQLite3 file.
      2. Converts DB to dictionary, collects relevant data.
      3. Walks the backup folder to map files to their SHA1 name.
    """
    if not os.path.isfile(file_path):
        logging.error(f'[x] The supplied file_path is invalid: {file_path}')
        return None

    if not is_sqlite3(file_path):
        logging.warning(f'[!] The following supplied file path is not SQLite3 -> {file_path}')
        return None

    # Convert the main manifest.db file to a dictionary
    sql_dict = convert_sqlite3_to_sql_dict(file_path)
    if not sql_dict:
        logging.warning('[!] No valid data found in the database.')
        return None

    # Build the output_database by iterating the SQL dictionary
    sms_db_hash = iterate_sql_dict(sql_dict, output_database, sms_database,
                                   url_block_list, url_set)

    # Walk the directory to map SHA1 to local paths
    file_walk_database = walk_the_backup(file_path)

    return sms_db_hash, file_walk_database

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main():
    start_time = time.time()

    # Parse CLI args
    args = parse_args()
    file_path = args.file_path

    # Initialize data structures
    output_database = {}
    sms_database = {}
    url_set = set()
    url_block_list = ['content.icloud.com']
    magic_generator = magic.Magic(flags=magic.MAGIC_MIME_TYPE)

    # Examine the primary manifest.db file
    sms_db_hash, file_walk_database = examine_and_process_db_file(
        file_path, 
        url_block_list, 
        url_set, 
        output_database, 
        sms_database
    ) or (None, {})

    # If valid data, proceed
    if output_database and file_walk_database:
        # Add MIME info and path data
        add_metadata_to_db_file(output_database, file_walk_database, magic_generator)

        # Potential usage examples (uncomment as needed):
        # filter_manifest_by_domain_str(output_database, 'RootDomain', print_report=True)
        # filter_manifest_by_mime_type(output_database, 'text/plain', print_report=True)
        # filter_manifest_by_sql_entry(output_database, 'sms.db', print_report=True)

        # # Copy images example:
        # images_dict = filter_manifest_by_mime_type(output_database, 'image', print_report=True)
        # copy_to_tmp(images_dict)

    # If we identified an sms.db in the main DB, we can parse it here too
    if sms_db_hash and sms_db_hash in output_database:
        sms_db_entry = output_database[sms_db_hash]
        # Examine the SMS database for URLs
        sms_db_path = sms_db_entry['path']
        if os.path.isfile(sms_db_path):
            # Convert SMS DB to dict, then filter for URLs
            sms_dict = convert_sqlite3_to_sql_dict(sms_db_path)
            for key, data_body in sms_dict.items():
                global_filter(data_body, url_block_list, 
                              lambda u, block_list: add_url(u, block_list, url_set))
        else:
            logging.warning(f'[!] SMS database path does not exist on disk: {sms_db_path}')

    # Write all discovered URLs to urls.txt
    process_url_file(url_set)

    # Print elapsed time
    print_elapsed_time(start_time)

if __name__ == '__main__':
    main()
