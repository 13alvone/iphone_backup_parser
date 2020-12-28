# iPhone Backup Parser
This is a basic script written to parse an iphone backup that is stored to a user's machine.  The initial intention of this script was to retreive all http links that I had sent to myself via SMS texts over the past several years. As I began processing the data produced from performing a local iPhone 11 (iOS 11.0.1) backup on an M1 Macbook (OSX 11.0.1), I added a lot of unused functionality to expand this script's usage in the future. This particular parser uses the python sqlite3 module to iterate through the manifest.db files which appears to define the internal structure of the stored backup.

NOTE: This is a purely experimental script with absolutely no warranty express or implied. Please use with caution and at your own risk.

## Usage

Proper usage requires that you, the user know the location of the iPhone backup's manifest file, which was found here for me:
>/Users/username/Library/Application Support/MobileSync/Backup/<backup_identifier>

`# Python3 -f <pathToManifest.db>`

## Artifacts
This script produces the `urls.txt` file and an optional copied collection of all images matching the `image` type. If this option is enabled within the `main()` function, all matching images will be copied into a newly created directory placed within your current working directory.

## Main() Re-Write Options and Examples [DIY]
#### Filter By Domain String Example
`filter_manifest_by_domain_str('RootDomain', print_report=True)`
#### Filter By MIME Extension Type Example
`filter_manifest_by_mime_type('text/plain', print_report=True)`
#### Filter By SQL Entry String Example
`filter_manifest_by_sql_entry('sms.db', print_report=True)`
#### Full Example of How to Copy All Images
`filter_manifest_by_mime_type('image', print_report=True)  copy_to_tmp(output_database)`

## Requirements
This particular parser uses the python sqlite3 module to iterate through the manifest.db files which appears to define the internal structure of the stored backup.

For other requirements not included in the general 3.9.1 python build, do:
`pip3 install -r requirements.txt`

## License
See the `License` file found within this project's root directory.
