#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on April 29 11:13 AM 2024
Created in PyCharm
Created as Cosmic_Bench_DAQ_Control/DAQController.py

@author: Dylan Neff, Dylan
"""

import os
import subprocess
from time import time, sleep


class DAQController:
    def __init__(self, subrun=None, out_dir=None, dream_daq_client=None):
        self.subrun = subrun or {}
        self.out_directory = out_dir
        self.out_name = self.subrun.get('sub_run_name')
        self.run_time = self.subrun.get('run_time', 10)  # minutes
        self.dream_daq_client = dream_daq_client
        self.original_working_directory = os.getcwd()

        self.run_start_time = None
        self.measured_run_time = None

        self.stop_dream_sh_path = './bash_scripts/stop_dream.sh'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.original_working_directory)

    def run(self):
        run_successful = True

        try:
            self.dream_daq_client.send('Start')
            self.dream_daq_client.send_json(self.subrun)
            res = self.dream_daq_client.receive()
            if res == '':
                raise ConnectionError('Dream DAQ server closed connection unexpectedly')
            if res != 'Dream DAQ starting':
                print(f'Error starting Dream DAQ: received "{res}"')
                return False
            self.run_start_time = time()

            res = self.dream_daq_client.receive()  # Wait for dream daq to finish
            if res != 'Dream DAQ stopped':
                print('Error stopping DAQ')
                return False

            self.measured_run_time = time() - self.run_start_time

            # RunCtrl can abort during FEU configuration (e.g. "WrRd_Missmatch", an
            # unreachable FEU) and still produce a normal 'Dream DAQ stopped' reply,
            # leaving 0-byte data files. Treat a stop far earlier than the requested
            # run_time as a failed start so daq_control retries the sub-run instead
            # of marking it complete. (A manual stop_run/stop_sub_run also ends early;
            # daq_control checks those flags before retrying, so it is not re-run.)
            requested_s = float(self.subrun.get('run_time', 0)) * 60
            if requested_s >= 120 and self.measured_run_time < min(60, 0.5 * requested_s):
                print(f'DAQ stopped after only {self.measured_run_time:.0f} s of a requested '
                      f'{requested_s:.0f} s — treating as a failed start, retrying in 30 s')
                run_successful = False
                sleep(30)
                return False

        except KeyboardInterrupt:
            print('Keyboard interrupt. Stopping DAQ process.')
            ret = subprocess.call([self.stop_dream_sh_path])
            if ret != 0:
                print('Error stopping Dream DAQ via stop_dream.sh script.')
            run_successful = False

            if self.run_start_time is not None:
                self.measured_run_time = time() - self.run_start_time
                run_successful = True  # Data taken before interrupt may be usable
            else:
                self.measured_run_time = 0
            res = self.dream_daq_client.receive()
            if res != 'Dream DAQ stopped':
                print('Error stopping Dream DAQ')
        finally:
            print('Dream Subrun complete.')
            if self.measured_run_time is None:
                if self.run_start_time is None:
                    self.measured_run_time = 0
                else:
                    self.measured_run_time = time() - self.run_start_time

            if run_successful:
                self.write_run_time()

        return run_successful

    def write_run_time(self):
        with open(f'{self.out_directory}/run_time.txt', 'w') as file:
            out_str = ''
            if self.measured_run_time is not None:
                out_str += f'Run Time: {self.measured_run_time:.2f} seconds'
            if self.run_start_time is not None:
                out_str += f'\nRun Start Time: {self.run_start_time}'
            if out_str != '':
                file.write(out_str)
            else:
                file.write('None')
