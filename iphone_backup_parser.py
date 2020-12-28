import subprocess
import plistlib
import argparse
import sqlite3
import logging
import magic
import math
import time
import re
import os

# Global Variables
start_time = time.time()
report_list = []
url_set = set()
output_database = {}
file_walk_database = {}
sms_db_hash = None
sms_database = {}
magic_generator = magic.Magic(flags=magic.MAGIC_MIME_TYPE)
url_block_list = [
    'content.icloud.com',
]


def is_sqlite3(_path):
    process = subprocess.run(['file', _path], check=True, stdout=subprocess.PIPE, universal_newlines=True)
    output = f'{process.stdout}'.lower()
    if 'sqlite' in output:
        return True
    else:
        return False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file_path', help='Target SQLite3 Path', type=str, required=True)
    arguments = parser.parse_args()
    return arguments


def print_elapsed_time(_start_time):
    seconds = round(int(time.time() - _start_time), 2)
    minutes = math.trunc(seconds / 60)
    remaining_seconds = math.trunc(seconds - (minutes * 60))
    if len(f'{remaining_seconds}') != 2:
        remaining_seconds = f'0{remaining_seconds}'
    elapsed_time = f'{minutes}:{remaining_seconds}'
    print(f'[i] Total_Time Elapsed: {elapsed_time}')


def convert_sqlite3_to_sql_dict(_path):
    result_dict = {}
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
            result_dict[key] = content
    return result_dict


def iterate_sql_dict(_sqlite3_dict):
    global report_list, sms_database
    for key in _sqlite3_dict:
        report_list.append(f'[+] Item: {key}\n')
        if isinstance(_sqlite3_dict[key], dict):
            iterate_sql_dict(_sqlite3_dict[key])
        else:
            data_body = _sqlite3_dict[key]
            report_list.append(f'[^] {data_body}\n')
            try:
                generate_cleaned_manifest_entry(data_body, print_item=False)    # Do Iterative Action From Here Down...
            except:
                pass
            if sms_db_hash:
                sms_database[key] = data_body


def global_filter(_obj):
    global url_set, url_allow_list
    if isinstance(_obj, int) or isinstance(_obj, str):
        re_extract_urls(_obj)
        return _obj
    elif isinstance(_obj, bytes):
        _obj_raw_ascii = _obj.decode('ascii', 'ignore')
        if 'bplist' in _obj_raw_ascii:
            try:
                _obj = plistlib.loads(_obj, fmt=None, dict_type=dict)
                re_extract_urls(_obj)
            except:
                pass
        return _obj
    elif isinstance(_obj, dict):
        re_extract_urls(_obj)
        for key in _obj:
            _obj[key] = global_filter(_obj[key])
        return _obj
    elif isinstance(_obj, list) or isinstance(_obj, tuple):
        re_extract_urls(_obj)
        new_list = []
        for item in _obj:
            new_list.append(global_filter(item))
        _obj = new_list
        return _obj
    elif isinstance(_obj, set):
        re_extract_urls(_obj)
        new_set = set()
        for item in _obj:
            new_set.add(global_filter(item))
        _obj = new_set
        return _obj


def generate_cleaned_manifest_entry(_data_body, print_item=True):
    global output_database, sms_db_hash
    serial = _data_body[0]
    directory_data = 'Unknown'
    data_type = 'Unknown'

    manifest_entry_dict = {
        'path': directory_data,
        'domain': _data_body[1],
        'sql_entry': _data_body[2],
        'unknown_number': _data_body[3],
        'data': _data_body[4],
        'type': data_type,
    }
    output_database[serial] = manifest_entry_dict
    try:
        if 'sms.db' in manifest_entry_dict['sql_entry']:
            sms_db_hash = serial
    except TypeError:
        pass

    if print_item:
        msg = f'{"-" * 50}\n[+] {serial}\n' \
              f'[^] Directory:\t{manifest_entry_dict["directory"]}\n' \
              f'[^] Domain:\t{manifest_entry_dict["domain"]}\n' \
              f'[^] SQL Entry:\t{manifest_entry_dict["sql_entry"]}\n' \
              f'[^] Unknown:\t{manifest_entry_dict["unknown_number"]}\n' \
              f'[^] Manifest Data:\t{manifest_entry_dict["manifest_data"]}\n' \
              f'[^] Type:\t{manifest_entry_dict["type"]}'
        print(msg)


def add_url(_url):
    global url_set, url_block_list
    for blocked_url in url_block_list:
        if blocked_url in _url:
            return None
    url_set.add(_url)


def re_extract_urls(_data):
    try:
        if isinstance(_data, list) or isinstance(_data, tuple) or isinstance(_data, set):
            for entry in _data:
                url_list = re.findall(r'(https?://\S+)', entry)
                for url in url_list:
                    add_url(url)
        elif isinstance(_data, dict):
            for key in _data:
                url_list0 = re.findall(r'(https?://\S+)', key)
                url_list1 = re.findall(r'(https?://\S+)', _data[key])
                for url in url_list0:
                    add_url(url)
                for url in url_list1:
                    add_url(url)
        elif isinstance(_data, str):
            url_list = re.findall(r'(https?://\S+)', _data)
            for url in url_list:
                add_url(url)
        elif isinstance(_data, bytes):
            url_list = re.findall(r'(https?://\S+)', _data.decode('ascii', 'ignore'))
            for url in url_list:
                add_url(url)
    except TypeError as e:
        logging.info(e)


def process_data_set(_sqlite3_dict, print_report=False):
    global report_list
    report_list.clear()
    iterate_sql_dict(_sqlite3_dict)
    if print_report:
        for entry in report_list:
            print(entry)


def walk_the_backup(_path):
    global file_walk_database
    target_path = '/'.join(_path.split('/')[:-1])
    for root, dirs, files in os.walk(target_path, topdown=False):
        for filename in files:
            full_path = f'{root}/{filename}'
            file_walk_database[filename] = full_path


def print_types_dict(_input_dict):
    for key in _input_dict:
        print(f'[+] MIME Type: {key}\t\t{_input_dict[key]}')


def filter_by_domain_str(_filter_str, print_types=False):
    global output_database
    result_dict = {}
    type_dict = {}
    for key in output_database:
        if output_database[key]['path'] != 'Unknown' and output_database[key]['domain'] == _filter_str:
            if print_types:
                print(f'[+] {key}\n[^] {output_database[key]}\n{"-" * 50}\n')
            result_dict[key] = output_database[key]
            if output_database[key]['type'] not in type_dict:
                type_dict[output_database[key]['type']] = 1
            elif output_database[key]['type'] in type_dict:
                type_dict[output_database[key]['type']] += 1
    if print_types:
        print_types_dict(type_dict)
    return result_dict


def filter_manifest_by_mime_type(_mime_type_str, print_report=False):     # This is a `contains` filter
    global output_database
    result_dict = {}
    type_dict = {}
    for key in output_database:
        if output_database[key]['path'] != 'Unknown' and _mime_type_str in output_database[key]['type']:
            if print_report:
                print(f'[+] {key}\n[^] {output_database[key]}\n{"-" * 50}\n')
            result_dict[key] = output_database[key]
            if output_database[key]['type'] not in type_dict:
                type_dict[output_database[key]['type']] = 1
            elif output_database[key]['type'] in type_dict:
                type_dict[output_database[key]['type']] += 1
    if print_report:
        print_types_dict(type_dict)
    return result_dict


def filter_manifest_by_sql_entry(_sql_entry_str, print_report=False):     # This is a `contains` filter
    global output_database
    result_dict = {}
    type_dict = {}
    for key in output_database:
        if output_database[key]['path'] != 'Unknown' and _sql_entry_str in output_database[key]['sql_entry']:
            if print_report:
                print(f'[+] {key}\n[^] {output_database[key]}\n{"-" * 50}\n')
            result_dict[key] = output_database[key]
            if output_database[key]['type'] not in type_dict:
                type_dict[output_database[key]['type']] = 1
            elif output_database[key]['type'] in type_dict:
                type_dict[output_database[key]['type']] += 1
    if print_report:
        print_types_dict(type_dict)
    return result_dict


def copy_to_tmp(_output_database):
    target_path = f'{time.strftime("%Y%m%d-%H%M%S")}_output'
    subprocess.run(f'mkdir {target_path}', shell=True, check=True, stdout=subprocess.PIPE)
    for key in _output_database:
        filename = output_database[key]['sql_entry'].split('/')[-1].replace(' ', '_')
        file_path = output_database[key]['path']
        cmd = f'cp "{file_path}" "{target_path}/{filename}"'
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE)


def examine_and_process_db_file(_file_path, print_report=False):
    global output_database
    output_database = {}
    if is_sqlite3(_file_path):
        sqlite3_dict = convert_sqlite3_to_sql_dict(_file_path)
        if print_report:
            process_data_set(sqlite3_dict, print_report=True)
        else:
            process_data_set(sqlite3_dict)
        walk_the_backup(_file_path)
    else:
        logging.info(f'[!] The following supplied file path is not SQLite3\n{_file_path}\n')


def add_metadata_to_db_file():
    global file_walk_database
    sha1_file_set = set(file_walk_database.keys())
    for key in output_database:
        if key in sha1_file_set:
            location = file_walk_database[key]
            file_type = magic_generator.id_filename(location)
            output_database[key]['path'] = location
            output_database[key]['type'] = file_type


def process_url_file():
    global sms_database, output_database, sms_database, url_set
    if sms_db_hash is not None:
        _path = output_database[sms_db_hash]['path']
        examine_and_process_db_file(_path)
        for key in sms_database:
            sms_database[key] = global_filter(sms_database[key])

    f_out = open('urls.txt', 'w')
    for url in url_set:
        f_out.write(f'{url}\n')
    f_out.close()


def main():
    global start_time
    args = parse_args()
    file_path = args.file_path

    examine_and_process_db_file(file_path)
    add_metadata_to_db_file()

    # filter_manifest_by_domain_str('RootDomain', print_report=True)    # Filter By Domain String Example
    # filter_manifest_by_mime_type('text/plain', print_report=True)     # Filter By MIME Extension Type Example
    # filter_manifest_by_sql_entry('sms.db', print_report=True)         # Filter By SQL Entry String Example

    # Copy Images Example
    # filter_manifest_by_mime_type('image', print_report=True)          # Filter Only Images for Image Copy Next
    # copy_to_tmp(output_database)                                      # Copy ALL MIME Image Type Files to /tmp

    process_url_file()
    print_elapsed_time(start_time)


if __name__ == "__main__":
    main()
