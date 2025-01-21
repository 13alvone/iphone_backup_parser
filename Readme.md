# iPhone Backup Parser

This script parses an iPhone backup manifest (`manifest.db`) found on a user’s machine. Its primary features include:
- Extracting and listing all HTTP and HTTPS links from SMS messages or any other tables in the backup database.
- Filtering parsed data by domain, MIME type, or specific strings within database entries.
- Copying files (such as images) matching certain criteria (e.g., `image` MIME type) into a local output folder.
- Logging all activity, including warnings and errors, using Python’s logging module.

## Usage
1. **Install Dependencies**  
	If you are missing `python-magic` or other modules, you may also need to install `libmagic` (for macOS: `brew install libmagic`):
		pip3 install python-magic

2. **Run the Script**  
		chmod +x iphone_backup_parser.py
		./iphone_backup_parser.py <pathToManifest.db>

3. **Command-Line Argument**  
	A single positional argument is required: the path to your `manifest.db`. For example:
		./iphone_backup_parser.py "/Users/username/Library/Application Support/MobileSync/Backup/<backupID>/Manifest.db"

## Output
- A `urls.txt` file containing all extracted URLs (excluding any blocklisted entries).
- Logs all processed data and errors to stdout with clear logging prefixes (`[i]` for info, `[!]` for warnings, `[x]` for errors).
- An optional feature lets you copy images (or other file types) from the backup into a time-stamped folder in your current directory.

## Examples
- Filtering by a specific domain:
		filter_manifest_by_domain_str(output_database, 'RootDomain', print_report=True)

- Filtering by MIME type:
		filter_manifest_by_mime_type(output_database, 'text/plain', print_report=True)

- Filtering by SQL entry:
		filter_manifest_by_sql_entry(output_database, 'sms.db', print_report=True)

- Copying images:
		images_dict = filter_manifest_by_mime_type(output_database, 'image', print_report=True)
		copy_to_tmp(images_dict)

## License
See the `License` file in this project’s root directory for further information.
