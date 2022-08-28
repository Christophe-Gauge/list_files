#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Recursively gather a list of files and directories for a given path
and processes files as needed.

Source: https://github.com/Christophe-Gauge/list_files
'''

# I M P O R T S ###############################################################

from __future__ import print_function
from __future__ import generators
import sys
import os
from queue import Queue
import threading
import datetime
import argparse
import traceback
import getpass
import time
import multiprocessing
import signal
import logging
from logging.handlers import RotatingFileHandler
import re

__author__ = "Videre Research, LLC."
__version__ = "1.0.5"
__license__ = "GNU General Public License v3.0"


# G L O B A L S ###############################################################


# Format is <current uid>: <new uid>
uid_to_change = {1001: 34273, 1002: 34313}
gid_to_change = {101: 10101, 100: 10045}
# user1 UID   1001 -> 34273
# user2 UID   1002 -> 34313
# group1 GID   101 -> 10101
# group2 GUD   100 -> 10045

directories_to_exclude = ['.snapshot']
files_to_exclude = ['.DS_Store']

num_threads = multiprocessing.cpu_count()

file_queue = Queue()
number_of_files_processed = 0
number_of_folders_processed = 0
number_of_files_modified = 0
number_of_folders_modified = 0
# transfer_total = 0
threadLock = threading.Lock()
is_done_listing_files = False
process_file_symbolic_links = False
before = None

intervals = (
    ('w', 604800),  # 60 * 60 * 24 * 7
    ('d', 86400),   # 60 * 60 * 24
    ('h', 3600),    # 60 * 60
    ('m', 60),
    ('s', 1),
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)
try:
    logFile = os.path.realpath(__file__).split('.')[0] + ".log"
    fh = RotatingFileHandler(logFile, maxBytes=(1048576 * 300), backupCount=7)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info("Log file:    %s" % logFile)
except Exception as e:
    logger.warning("Unable to log to file: %s - %s" % (logFile, e))
logger.info("-" * 80)
logger.info("Version:  %s" % (__version__))
logger.info("Path:    %s" % (os.path.realpath(__file__)))


# F U N C T I O N S ###########################################################


def display_time(seconds, granularity=2):
    """Display time with the appropriate unit."""
    result = []
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{0:.0f}{1}".format(value, name))
    return ' '.join(result[:granularity])


def handler_stop_signals(signum, frame):
    """Handles the SIGTERM signal to stop script cleanly."""
    logger.info("Received %s signal, exiting." % signum)
    sys.exit(0)


def total_seconds(dt):
    # Keep backward compatibility with Python 2.6 which doesn't have
    # this method
    if hasattr(datetime, 'total_seconds'):
        return dt.total_seconds()
    else:
        return (dt.microseconds + (dt.seconds + dt.days * 24 * 3600) * 10**6) / 10**6


def GetHumanReadable(size, precision=2):
    """Transform file size to human readable number."""
    suffixes = [' B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1  # increment the index of the suffix
        size = size / 1024.0  # apply the division
    return "%.*f %s" % (precision, size, suffixes[suffixIndex])


def ProcessFileThread(i, q):
    """This is the worker thread function that will process files in the queue."""
    global number_of_files_processed
    global number_of_files_modified
    global number_of_folders_processed
    global number_of_folders_modified
    global is_done_listing_files
    global before
    # global transfer_total
    is_done_processing = False
    while not is_done_processing:
        if q.empty():
            if is_done_listing_files:
                is_done_processing = True
                break
            else:
                logger.debug('%s - No files to process, thread waiting' % (i))
                time.sleep(7)
        else:
            item = q.get()
            if item is None:
                pass
            else:
                # print('%s - %s files left' % (i, q.qsize()))
                if not os.path.exists(item):
                    logger.error(item + ' does not exist')
                else:
                    with threadLock:
                        if os.path.isdir(item):
                            number_of_folders_processed += 1
                        else:
                            number_of_files_processed += 1
                            # transfer_total += float(os.path.getsize(item))
                    try:
                        full_file_name = os.path.basename(item)
                        file_path = os.path.dirname(item)
                        if full_file_name in files_to_exclude:
                            logger.warning(f'File {item} is in exclude list')
                        
                        # =============== IF RENAMING FILES ===============
                        # We're not renaming directories because if will result in outdated file list in the queue
                        if os.path.isdir(item):
                            continue
                        # We're not processing hidden files, you can if you want
                        if full_file_name.startswith('.'):
                            continue

                        name_extension = os.path.splitext(full_file_name)
                        short_file_name = name_extension[0]
                        file_extension = name_extension[1]
                        # Just removing dashes from the file name, adjust as needed
                        new_file_name = short_file_name.replace(' - ', '').strip()
                        if new_file_name != '' and short_file_name != new_file_name:
                            new_file_name += file_extension
                            logger.info(f'File renamed: {item} -> {new_file_name}')
                            os.rename(item, os.path.join(file_path, new_file_name))
                            with threadLock:
                                number_of_files_modified += 1

                        # =============== IF CHANGING FILE OWNERSHIP ===============
                        # need_to_be_changed = False
                        # if os.path.islink(item):
                        #     st = os.lstat(item)
                        # else:
                        #     st = os.stat(item)
                        # logger.debug("{0:<2d} - mode: {1:<10} uid: {2:<10} gid: {3:<10} {4:<35}".format(i, str(oct(st.st_mode))[-4:], st.st_uid, st.st_gid, item))
                        # if st.st_uid in uid_to_change:
                        #     need_to_be_changed = True
                        #     new_uid = uid_to_change[st.st_uid]
                        #     logger.debug('%s - UID of %s will be changed to %s' % (i, st.st_uid, new_uid))
                        # else:
                        #     new_uid = st.st_uid
                        # if st.st_gid in gid_to_change:
                        #     need_to_be_changed = True
                        #     new_gid = gid_to_change[st.st_gid]
                        #     logger.debug('%s GID of %s will be changed to %s' % (i, st.st_gid, new_gid))
                        # else:
                        #     new_gid = st.st_gid
                        # if need_to_be_changed:
                        #     if os.path.islink(item):
                        #         os.lchown(item, new_uid, new_gid)
                        #         os.chown(item, new_uid, new_gid)
                        #     else:
                        #         os.chown(item, new_uid, new_gid)
                        #     # st = os.stat(item)
                        #     # if st.st_uid == new_uid and st.st_gid == new_gid:
                        #     logger.debug('%s - %s changed UID: %s -> %s  GID: %s -> %s' % (i, item, st.st_uid, new_uid, st.st_gid, new_gid))
                        #     # else:
                        #     #     logger.error('%s - %s failed to change UID: %s - %s  GID: %s - %s' % (i, item, st.st_uid, new_uid, st.st_gid, new_gid))
                        #     with threadLock:
                        #         if os.path.isdir(item):
                        #             number_of_folders_modified += 1
                        #         else:
                        #             number_of_files_modified += 1
                        after3 = datetime.datetime.now()
                        sys.stdout.write("\rProcessed {0:,} files in {1:,} directories, {2:,} files modified in {3}.".format(number_of_files_processed, number_of_folders_processed, number_of_files_modified, display_time(total_seconds(after3 - before))))
                        sys.stdout.flush()
                    except Exception as e:
                        logger.error('%s - failed to change: %s' % (i, item))
                        logger.error("Error {0}".format(str(e)))
                        logger.error(traceback.format_exc())
                    q.task_done()
    logger.info('%s - Thread DONE' % i)
    sys.exit(0)


def dirlist(q, base_path):
    """Add files and folders to the queue."""
    global is_done_listing_files
    before2 = datetime.datetime.now()
    for elem in dirwalk(base_path):
        # logger.debug(elem)
        q.put(elem)
    logger.info('Thread 0: DONE gathering list of files')
    after2 = datetime.datetime.now()
    logger.info('Duration of dirlist %s' % display_time(total_seconds(after2 - before2)))
    is_done_listing_files = True
    sys.exit(0)


def dirwalk(dir):
    """Recursively walk a directory tree, using a generator. Don't process directories that are links."""
    global process_file_symbolic_links
    for f in os.listdir(dir):
        fullpath = os.path.join(dir, f)
        if not os.path.islink(fullpath) or (os.path.islink(fullpath) and process_file_symbolic_links):
            yield fullpath
            if os.path.isdir(fullpath):
                if os.path.basename(fullpath) in directories_to_exclude:
                    logger.warning('Directory %s is in exclude list' % fullpath)
                elif os.path.islink(fullpath):
                    logger.warning('Skipping link directory %s' % fullpath)
                else:
                    try:
                        for x in dirwalk(fullpath):  # recurse into subdir
                            yield x
                    except Exception as e:
                        logger.error("Error {0}".format(str(e)))
                        logger.error(traceback.format_exc())
        else:
            logger.warning('Skipping link %s' % fullpath)


def main():
    """Main function."""
    global number_of_files_processed
    global number_of_files_modified
    global number_of_folders_processed
    global number_of_folders_modified
    global before
    global process_file_symbolic_links
    signal.signal(signal.SIGINT, handler_stop_signals)
    signal.signal(signal.SIGTERM, handler_stop_signals)

    parser = argparse.ArgumentParser(description='Recursively process files and folders.')
    parser.add_argument('directory_path', metavar='path', type=str, nargs='+',
                        help='the path of the folder to be processed')

    parser.add_argument(
        '-v', '--verbose', action='store_true',
        required=False, default=False,
        help='Output debug detail.')

    parser.add_argument(
        '-l', '--links', action='store_true',
        required=False, default=False,
        help='Process files that are symbolic links.')

    args = parser.parse_args()

    if args.verbose:
        logger.info('Verbose option passed, will show debug output')
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
    if args.links:
        process_file_symbolic_links = True

    base_path = os.path.abspath(args.directory_path[0])
    if not os.path.exists(base_path):
        logger.error('%s does not exist' % (base_path))
        sys.exit(1)

    if not os.path.isdir(base_path):
        logger.error('%s is NOT a directory' % (base_path))
        sys.exit(1)

    logger.info('Recursively processing files in %s' % (base_path))
    logger.info('Will create %s threads' % (num_threads))
    # logger.info('UID change list: %s' % (str(uid_to_change)))
    # logger.info('GID change list: %s' % (str(gid_to_change)))
    try:
        user = os.getlogin()
    except OSError as e:
        user = 'nobody'
    except Exception as e:
        user = 'unknown'
        logger.error("Error {0}".format(str(e)))
        logger.error(traceback.format_exc())
    if user != getpass.getuser():
        user = "%s as %s" % (user, getpass.getuser())
    logger.info("User:    %s\n" % (user))
    before = datetime.datetime.now()

    worker = threading.Thread(target=dirlist, args=(file_queue, base_path,))
    worker.setDaemon(True)
    worker.start()

    time.sleep(1)

    for i in range(num_threads):
        worker = threading.Thread(target=ProcessFileThread, args=(i + 1, file_queue,))
        worker.setDaemon(True)
        worker.start()

    logger.info('*** Main thread waiting')
    worker.join()
    logger.info('*** Main thread Done')
    time.sleep(1)
    after = datetime.datetime.now()
    logger.info('Duration  %s' % display_time(total_seconds(after - before)))

    logger.info('Processed {0:,} files'.format(number_of_files_processed))
    logger.info('Processed {0:,} directories'.format(number_of_folders_processed))
    logger.info('Modified  {0:,} files'.format(number_of_files_modified))
    logger.info('Modified  {0:,} directories'.format(number_of_folders_modified))
    # logger.info('%s' % GetHumanReadable(transfer_total))

    sys.stdout.flush()
    sys.stdout.close()

    sys.stderr.flush()
    sys.stderr.close()
    sys.exit(0)


###############################################################################

if __name__ == "__main__":
    main()

# E N D   O F   F I L E #######################################################
