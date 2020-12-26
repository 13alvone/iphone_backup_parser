import subprocess
import argparse
import sqlite3

# Global Variables
data_set = set()
report_list = []


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
    global data_set, report_list
    for key in _sqlite3_dict:
        report_list.append(f'[+] Item: {key}\n')
        if isinstance(_sqlite3_dict[key], dict):
            iterate_sql_dict(_sqlite3_dict[key])
        else:
            data_body = _sqlite3_dict[key]
            report_list.append(f'[^] {data_body}\n')
            ## DO THINGS HERE FOR ITERATOR. DATA AT THIS POINT IS A TUPLE
            # OLD: data_set.add(data_body[1])
            for item in data_body:
                if isinstance(item, bytes):
                    ascii_data = ascii(item)
                    print(ascii_data)


def process_data_set(_sqlite3_dict, print_output=False):
    global data_set, report_list
    data_set.clear()
    report_list.clear()
    iterate_sql_dict(_sqlite3_dict)
    if print_output:
        for entry in report_list:
            print(entry)
    return data_set


def main():
    global data_set
    args = parse_args()
    file_path = args.file_path
    if is_sqlite3(file_path):
        sqlite3_dict = convert_sqlite3_to_sql_dict(file_path)
        output_data_set = process_data_set(sqlite3_dict)
        for item in output_data_set:
            print(item)
    else:
        print('test')
        print(f'[!] The following supplied file path is not SQLite3\n{file_path}\n')


if __name__ == "__main__":
    main()
