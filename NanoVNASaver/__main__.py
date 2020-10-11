#! /bin/env python
#
#  NanoVNASaver
#
#  A python program to view and export Touchstone data from a NanoVNA
#  Copyright (C) 2019, 2020  Rune B. Broberg
#  Copyright (C) 2020 NanoVNA-Saver Authors
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
NanoVNASaver

A multiplatform tool to save Touchstone files from the
NanoVNA, sweep frequency spans in segments to gain more
data points, and generally display and analyze the
resulting data.
"""
import argparse
import logging
import sys

from NanoVNASaver.About import VERSION, INFO
from NanoVNASaver.NanoVNASaver_command import NanoVNASaver


def main():
    global args
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Set loglevel to debug")
    parser.add_argument("-D", "--debug-file",
                        help="File to write debug logging output to")
    parser.add_argument("--version", action="version",
                        version=f"NanoVNASaver {VERSION}")
    parser.add_argument("-o", "--output", type=str,
                    help="output location (folder)")
    parser.add_argument("-f", "--start", type=int,
                    help="start frequency in Hz")
    parser.add_argument("-t", "--stop", type=int,
                    help="stop frequency in Hz")
    parser.add_argument("-i", "--infinite", action="store_true",
                    help="infinite saving 2port touchstone files, otherwise once")

    args = parser.parse_args()

#    print("infinite",args.infinite)

    console_log_level = logging.WARNING
    file_log_level = logging.DEBUG

    print(INFO)

    if args.debug:
        console_log_level = logging.DEBUG

    logger = logging.getLogger("NanoVNASaver")
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(console_log_level)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if args.debug_file:
        fh = logging.FileHandler(args.debug_file)
        fh.setLevel(file_log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    logger.info("Startup...")

    window = NanoVNASaver()
    

if __name__ == '__main__':
    main()
