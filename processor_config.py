#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone processor configuration for Cosmic Bench.
Edit the constants below, then run this script to regenerate config/processor_config.json.
The flask UI's Start Processor button reads that JSON to launch processor_watcher.py.
"""

import json
import os

from run_config import BASE_DATA_DIR

# --- Paths ---
BASE_DATA = f'{BASE_DATA_DIR}Run/'
# BASE_DATA = '/mnt/cosmic_data/clas12/Run/'
MM_BUILD = '/local/home/usernsw/mm_dream_reconstruction/build'

M3_TRACKING_DIR = '/local/home/usernsw/cosmic_bench_m3_tracking/'

CONFIG = {
    # Top-level directory containing all run_N/ subdirectories
    'runs_dir': f'{BASE_DATA}',

    # Subdirectory names (must match what daq_control.py creates)
    'raw_daq_inner_dir':        'raw_daq_data',
    'decoded_root_inner_dir':   'decoded_root',
    'hits_inner_dir':           'hits_root',
    'combined_hits_inner_dir':  'combined_hits_root',
    'm3_tracking_inner_dir':    'm3_tracking_root',
    'filtered_root_inner_dir':  'filtered_root',

    # C++ executables from mm_strip_reconstruction
    'decode_executable':  f'{MM_BUILD}/decoder/decode',
    'analyze_executable': f'{MM_BUILD}/waveform_analysis/analyze_waveforms',
    'combine_executable': f'{MM_BUILD}/feu_hit_combiner/combine_feus_hits',

    # Pipeline stages to run
    'do_decode':  True,
    'do_analyze': True,
    'do_combine': True,

    # Common-noise subtraction (median across each 64-channel block, per sample) during
    # waveform analysis. NB: the pedestal RMS is ALWAYS computed after CNS in the processor;
    # this flag only toggles CNS on the DATA waveforms.
    'common_noise_subtraction': True,

    # M3 tracker configuration
    # Set m3_feu_num to the FEU number of the M3 detector, or null to disable M3 handling
    'm3_feu_num':       1,
    'do_m3_tracking':   True,
    'tracking_sh_path': f'{M3_TRACKING_DIR}run_tracking_single.sh',
    'tracking_run_dir': M3_TRACKING_DIR,

    # Set filter_by_m3 to true to filter decoded data by M3 traversal events
    'filter_by_m3': False,

    # Cleanup options
    'save_fdfs':    True,  # Keep raw FDF files after processing
    'save_decoded': True,  # Keep decoded ROOT files after filtering/analysis

    # Detector geometry for M3 filtering.
    # If null, the watcher will load detector info from each run's run_config.json automatically.
    'detectors':          None,
    'included_detectors': None,
    'detector_info_dir':  '/mnt/cosmic_data/config/detectors/',

    # Pedestal location:
    #   'same'  - pedestal FDFs are in raw_daq_data/ alongside data FDFs
    #   'abs'   - fixed absolute path given by pedestal_dir
    #   'find'  - read pedestal_run.txt from raw_daq_data/ and look up pedestal_dir/<name>/pedestals_noise/
    'pedestal_loc': 'same',
    'pedestal_dir': None,

    # Shell commands to set up the C++ environment (ROOT + devtoolset) for decode/analyze/combine.
    # Run in a login bash shell at watcher startup; the captured env dict is passed to all
    # C++ subprocess calls.  M3 tracking always runs in the default process env (no ROOT sourced).
    'cpp_setup_script': (
        'source ~/root_6_30_02/root-build/bin/thisroot.sh && '
        'source scl_source enable devtoolset-9'
    ),

    # Run filtering: process only specific runs or exclude certain runs by directory name.
    # If include_runs is a non-empty list, only those run directories are processed.
    # If exclude_runs is a non-empty list, those run directories are skipped.
    # Both null/empty means process all runs as normal.
    # 11-26-26: only the det2 efficiency batch 2 run (earlier det2 runs already processed).
    'include_runs': ['p2_det2_efficiency_batch2_430_11-26-26'],  # e.g. ['run_42', 'run_43'] — only process these runs
    'exclude_runs': None,  # e.g. ['run_1', 'run_2']  — skip these runs

    # Watcher behavior
    'poll_interval':  30,  # seconds between full directory scans
    'stale_run_days':  4,  # runs with no new FDFs for this many days are checked once then skipped
    'free_threads':    2,  # CPU threads to leave free during parallel processing
}

if __name__ == '__main__':
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'processor_config.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(CONFIG, f, indent=4)
    print(f'Written: {out_path}')
