# list_files.py

[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
![pypi](https://img.shields.io/pypi/v/pybadges.svg)
![versions](https://img.shields.io/pypi/pyversions/pybadges.svg)

> A multithreaded, fast and efficient way of recursively processing a large number of files and directories in Python.

This efficient script leverages multithreading and the use of a queue to store a list of work to be done. One thread recursively parses the filesystem to get a list of files and folders to be processed and populates that information in a queue. Additional threads wait for the queue to be populated with information and process each file and directory as needed. This allows for the processing of the files to start without having to wait for the full list of files to be complete, resulting in faster processing time.
The number of threads is based on the number of CPU cores on the system. Depending on the size of the system you are running this script on and how expansive the file operation is, you may not need that many threads, please adjust accordingly.
This script can be used for many different purposes, from uploading files to object storage to renaming files to changing the UID and/or GID on a Linux system, the possibilities are endless. There are some obvious caveats if renaming files and folders, if you rename a parent folder then the path recorded in the queue will obviously no longer be valid, so adjust the script as needed!
The sample processing included in this script simply removes dashed from the file names, but you should easily be able to adjust to your other needs. Another example provided (commented out) is to modify the GID and UID of files and directories on a Linux filesystem, based on a given old -> new set of tuples, so please also adjust as needed.


Additional details are available at:

https://technotes.videre.us/en/python/processing-files-and-folders/


## Usage

```
list_files.py
usage: list_files.py [-h] [-v] [-l] path [path ...]

Recursively process files and folders.

positional arguments:
 path the path of the folder to be processed

optional arguments:
 -h, --help show this help message and exit
 -v, --verbose Output debug detail.
 -l, --links Process files that are symbolic links.
 ```
