import subprocess
import plistlib
import argparse
import sqlite3
import logging
import re
import os

# Global Variables
data_set = set()
report_list = []
url_set = set()
output_database = {}
type_set = set()
sql_entry_set = set()
file_walk_database = {}


def is_sqlite3(_path):
    process = subprocess.run(['file', _path], check=True, stdout=subprocess.PIPE, universal_newlines=True)
    output = f'{process.stdout}'.lower()
    print(output)
    if 'sqlite' in output:
        return True
    else:
        return False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file_path', help='Target SQLite3 Path', type=str, required=True)
    arguments = parser.parse_args()
    return arguments


def convert_sqlite3_to_sql_dict(_path):
    output_dict = {}
    conn = sqlite3.connect(_path)
    cursor = conn.cursor()
    cursor.execute('SELECT name from sqlite_master where type="table"')
    tables = cursor.fetchall()
    for table in tables:
        table_name = table[0]
        qry = f'SELECT * from "{table_name}"'
        cursor.execute(qry)
        contents = cursor.fetchall()
        for content in contents:
            uuid = content[0]
            key = f'{table_name}_{uuid}'
            output_dict[key] = content
    return output_dict


def iterate_sql_dict(_sqlite3_dict):
    global data_set, report_list, url_set
    for key in _sqlite3_dict:
        report_list.append(f'[+] Item: {key}\n')
        # re_extract_urls(key)
        if isinstance(_sqlite3_dict[key], dict):
            iterate_sql_dict(_sqlite3_dict[key])
        else:
            data_body = _sqlite3_dict[key]
            report_list.append(f'[^] {data_body}\n')
            # DO THINGS HERE FOR ITERATOR. DATA AT THIS POINT IS A TUPLE
            generate_cleaned_manifest_entry(data_body, print_item=False)


def generate_cleaned_manifest_entry(_data_body, print_item=True):
    global output_database, type_set
    sha1_hash = _data_body[0]
    directory_data = 'Unknown'
    data_type = 'Unknown'
    plist_data = plistlib.loads(_data_body[4], fmt=None, dict_type=dict)    # fmt=None - Autodetect Binary or XML
    manifest_entry_dict = {
        'directory': f'{directory_data}',
        'domain': f'{_data_body[1]}',
        'sql_entry': f'{_data_body[2]}',
        'unknown_number': f'{_data_body[3]}',
        'manifest_data': plist_data,
        'type': f'{data_type}',
    }
    output_database[sha1_hash] = manifest_entry_dict
    if print_item:
        msg = f'{"-" * 50}\n[+] {sha1_hash}\n' \
              f'[^] Directory:\t{manifest_entry_dict["directory"]}\n' \
              f'[^] Domain:\t{manifest_entry_dict["domain"]}\n' \
              f'[^] SQL Entry:\t{manifest_entry_dict["sql_entry"]}\n' \
              f'[^] Unknown:\t{manifest_entry_dict["unknown_number"]}\n' \
              f'[^] Manifest Data:\t{manifest_entry_dict["manifest_data"]}\n' \
              f'[^] Type:\t{manifest_entry_dict["type"]}'
        print(msg)


def re_extract_urls(_data):
    global url_set
    if isinstance(_data, list) or isinstance(_data, tuple):
        for list_entry in _data:
            url_list = re.findall(r'(https?://\S+)', list_entry)
            for url in url_list:
                url_set.add(url)
    elif isinstance(_data, dict):
        for key in _data:
            url_list0 = re.findall(r'(https?://\S+)', key)
            url_list1 = re.findall(r'(https?://\S+)', _data[key])
            for url in url_list0:
                url_set.add(url)
            for url in url_list1:
                url_set.add(url)
    elif isinstance(_data, str):
        url_list = re.findall(r'(https?://\S+)', _data)
        for url in url_list:
            url_set.add(url)
    elif isinstance(_data, bytes):
        url_list = re.findall(r'(https?://\S+)', _data.decode('ascii', 'ignore'))
        for url in url_list:
            url_set.add(url)
    else:
        pass


def process_data_set(_sqlite3_dict, print_output=False):
    global data_set, report_list
    data_set.clear()
    report_list.clear()
    iterate_sql_dict(_sqlite3_dict)
    if print_output:
        for entry in report_list:
            print(entry)
    return data_set


def walk_the_backup(_path):
    global file_walk_database
    target_path = '/'.join(_path.split('/')[:-1])
    for root, dirs, files in os.walk(target_path, topdown=False):
        for filename in files:
            full_path = f'{root}/{filename}'
            file_walk_database[filename] = full_path


def main():
    global data_set, url_set, type_set, output_database, sql_entry_set, file_walk_database
    args = parse_args()
    file_path = args.file_path

    if is_sqlite3(file_path):
        sqlite3_dict = convert_sqlite3_to_sql_dict(file_path)
        process_data_set(sqlite3_dict)
        walk_the_backup(file_path)
    else:
        logging.info(f'[!] The following supplied file path is not SQLite3\n{file_path}\n')

    sha1_file_set = set(file_walk_database.keys())
    for key in output_database:
        if key in sha1_file_set:
            location = file_walk_database[key]
            process = subprocess.run(['file', location], check=True, stdout=subprocess.PIPE, universal_newlines=True)
            file_type = f'{process.stdout}'.lower()
            output_database[key]['directory'] = location
            output_database[key]['type'] = file_type

    temp_filter = 'MediaDomain'
    for key in output_database:
        if output_database[key]['directory'] != 'Unknown' and output_database[key]['domain'] == temp_filter:
            print(f'[+] {key}\n[^] {output_database[key]}\n{"-" * 50}\n')


if __name__ == "__main__":
    main()
