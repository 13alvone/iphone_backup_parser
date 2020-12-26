#iPhone Backup Parser
This is a basic script written to parse an iphone backup that is stored to a user's machine.  This particular parser  uses the python sqlite3 module to iterate through the manifest.db files which appears to define the internal structure of the stored backup.

NOTE: This is a purely experimental script with absolutely no warranty express or implied. Please use with caution and at your own risk.

##Usage
`# Python3 -f <pathToManifest.db>`