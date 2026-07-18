#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autonomous on-the-fly processor watcher for Cosmic Bench DREAM DAQ data.

Watches all runs under a top-level runs directory and runs the
decode → (M3 filter) → analyze_waveforms → combine_feus_hits pipeline
on each new FDF file group as it becomes available.  Runs completely
independently of daq_control.py; start/stop from the flask UI or command line.

M3 FEU files are routed to the M3 tracking step (via shell script) rather
than the mm_strip_reconstruction decode pipeline.  If filter_by_m3 is enabled,
decoded non-M3 ROOT files are filtered by M3 traversal events before analysis.

Usage:
    python processor_watcher.py <processor_config_json_path>

Config keys (see processor_config.py to generate the JSON):
  runs_dir                : top-level directory containing run_N/ subdirs
  raw_daq_inner_dir       : subdir name for raw FDF files          (default: 'raw_daq_data')
  decoded_root_inner_dir  : subdir name for decoded ROOT files      (default: 'decoded_root')
  hits_inner_dir          : subdir name for per-FEU hit files       (default: 'hits_root')
  combined_hits_inner_dir : subdir name for combined hits           (default: 'combined_hits_root')
  m3_tracking_inner_dir   : subdir name for M3 tracking ROOT files  (default: 'm3_tracking_root')
  filtered_root_inner_dir : subdir name for M3-filtered ROOT files  (default: 'filtered_root')

  decode_executable       : path to the 'decode' binary
  analyze_executable      : path to the 'analyze_waveforms' binary  (optional)
  combine_executable      : path to the 'combine_feus_hits' binary  (optional)

  do_decode               : run decode step              (default: true)
  do_analyze              : run waveform analysis         (default: true)
  do_combine              : combine per-FEU hits          (default: true)

  m3_feu_num              : FEU number of the M3 tracker (int or null for no M3)
  do_m3_tracking          : run M3 tracking for M3 FEU files       (default: false)
  tracking_sh_path        : path to reference M3 tracking shell script
  tracking_run_dir        : working directory for M3 tracking program
  filter_by_m3            : filter decoded files by M3 traversal   (default: false)
  save_fdfs               : keep FDF files after processing         (default: true)
  save_decoded            : keep decoded ROOT files after filtering (default: true)

  detectors               : detector list for M3 geometry filter (or null to load from run_config.json)
  included_detectors      : which detectors to include in M3 filter (or null = all non-m3)
  detector_info_dir       : directory containing detector JSON info files

  pedestal_loc            : 'same' | 'abs' | 'find'
  pedestal_dir            : base pedestal dir (for 'abs' or 'find' modes)
  include_runs            : list of run directory names to process exclusively (null = all)
  exclude_runs            : list of run directory names to skip (null = none skipped)
  poll_interval           : seconds between full directory scans    (default: 30)
  stale_run_days          : runs with no new FDFs for this many days are skipped  (default: 4)
  free_threads            : CPU threads to leave free during processing (default: 2)
"""

import os
import sys
import json
import re
import time
import tempfile
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_functions import create_dir_if_not_exist


def main():
    if len(sys.argv) != 2:
        print("Usage: python processor_watcher.py <processor_config_json_path>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        config = json.load(f)

    run_watcher(config)


# ---------------------------------------------------------------------------
# Main watcher loop
# ---------------------------------------------------------------------------

def run_watcher(config: dict):
    runs_dir       = Path(config['runs_dir'])
    raw_inner      = config.get('raw_daq_inner_dir',        'raw_daq_data')
    decoded_inner  = config.get('decoded_root_inner_dir',   'decoded_root')
    hits_inner     = config.get('hits_inner_dir',           'hits_root')
    combined_inner = config.get('combined_hits_inner_dir',  'combined_hits_root')
    m3_track_inner = config.get('m3_tracking_inner_dir',    'm3_tracking_root')
    filtered_inner = config.get('filtered_root_inner_dir',  'filtered_root')

    decode_exe  = config.get('decode_executable',  '')
    analyze_exe = config.get('analyze_executable', '')
    combine_exe = config.get('combine_executable', '')

    do_decode  = config.get('do_decode',  True) and bool(decode_exe)
    do_analyze = config.get('do_analyze', True) and bool(analyze_exe)
    do_combine = config.get('do_combine', True) and bool(combine_exe)
    common_noise_subtraction = config.get('common_noise_subtraction', True)

    m3_feu_num       = config.get('m3_feu_num', None)
    do_m3_tracking   = config.get('do_m3_tracking', False) and m3_feu_num is not None
    tracking_sh_path = config.get('tracking_sh_path', '')
    tracking_run_dir = config.get('tracking_run_dir', '')
    filter_by_m3     = config.get('filter_by_m3', False) and do_m3_tracking
    save_fdfs        = config.get('save_fdfs', True)
    save_decoded     = config.get('save_decoded', True)

    detectors          = config.get('detectors', None)
    included_detectors = config.get('included_detectors', None)
    detector_info_dir  = config.get('detector_info_dir', None)

    pedestal_loc      = config.get('pedestal_loc', 'same')
    pedestal_base_dir = config.get('pedestal_dir', '') or ''

    include_runs   = set(config['include_runs']) if config.get('include_runs') else None
    exclude_runs   = set(config['exclude_runs']) if config.get('exclude_runs') else set()

    poll_interval  = config.get('poll_interval',  30)
    stale_run_days = config.get('stale_run_days',  4)
    free_threads   = config.get('free_threads',    2)
    n_threads      = max(1, (os.cpu_count() or 1) - free_threads)

    cpp_setup = config.get('cpp_setup_script', '')
    cpp_env   = _build_cpp_env(cpp_setup) if cpp_setup else None

    _check_binaries(do_decode, decode_exe, do_analyze, analyze_exe,
                    do_combine, combine_exe, do_m3_tracking, tracking_sh_path)

    print(f"[watcher] runs_dir      : {runs_dir}")
    if include_runs:
        print(f"[watcher] include_runs  : {sorted(include_runs)}")
    if exclude_runs:
        print(f"[watcher] exclude_runs  : {sorted(exclude_runs)}")
    print(f"[watcher] pipeline      : decode={do_decode}  analyze={do_analyze}  combine={do_combine}")
    print(f"[watcher] m3            : tracking={do_m3_tracking}  filter={filter_by_m3}  feu={m3_feu_num}")
    print(f"[watcher] threads       : {n_threads}  poll={poll_interval}s  stale_after={stale_run_days}d")
    print(f"[watcher] pedestal      : loc={pedestal_loc}  base={pedestal_base_dir or '(same as raw)'}")
    print(f"[watcher] cpp_env       : {'built from cpp_setup_script' if cpp_env else 'default process env'}")

    checked_stale_runs: set = set()
    prev_sizes: dict = {}

    while True:
        found_new = False

        if not runs_dir.exists():
            print(f"[watcher] Waiting for runs_dir: {runs_dir}")
        else:
            for run_dir in sorted(runs_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                if include_runs is not None and run_dir.name not in include_runs:
                    continue
                if run_dir.name in exclude_runs:
                    continue
                if run_dir.name in checked_stale_runs:
                    continue

                # Skip run dirs we cannot read (e.g. owned by another user or not
                # made by the current DAQ) so a PermissionError from iterdir()
                # below does not crash the whole watcher.
                if not os.access(run_dir, os.R_OK | os.X_OK):
                    print(f"[watcher] Skipping unreadable run dir: {run_dir.name}")
                    checked_stale_runs.add(run_dir.name)
                    continue

                is_stale = _run_is_stale(run_dir, raw_inner, stale_run_days)

                # Load detector info from run_config.json if not set in processor config
                run_detectors, run_included = detectors, included_detectors
                if filter_by_m3 and run_detectors is None:
                    run_detectors, run_included = _load_detector_info_from_run(run_dir)

                for subrun_dir in sorted(run_dir.iterdir()):
                    if not subrun_dir.is_dir():
                        continue

                    raw_dir = subrun_dir / raw_inner
                    if not raw_dir.exists():
                        continue

                    ped_dir = _resolve_pedestal_dir(raw_dir, pedestal_loc, pedestal_base_dir)

                    if do_decode and ped_dir:
                        _decode_pedestals(ped_dir, decode_exe, cpp_env)

                    all_fnums  = _get_data_file_nums(raw_dir)
                    done_fnums = _get_processed_file_nums(
                        subrun_dir, combined_inner, hits_inner, decoded_inner, filtered_inner,
                        m3_track_inner, do_combine, do_analyze, filter_by_m3, do_m3_tracking,
                        m3_feu_num
                    )

                    for fnum in sorted(all_fnums - done_fnums):
                        all_fdf_group = [
                            raw_dir / f for f in os.listdir(raw_dir)
                            if f.endswith('.fdf') and '_datrun_' in f
                            and _extract_file_num(f) == fnum
                        ]
                        if not all_fdf_group:
                            continue

                        key = (run_dir.name, subrun_dir.name, fnum)
                        current = {p.name: p.stat().st_size for p in all_fdf_group if p.exists()}
                        if not current or any(s == 0 for s in current.values()):
                            prev_sizes[key] = current
                            continue

                        if prev_sizes.get(key) == current:
                            print(f"\n[watcher] {run_dir.name}/{subrun_dir.name}  "
                                  f"file_num={fnum:03d}  ({len(all_fdf_group)} FEU(s))")
                            _process_file_num(
                                fnum, all_fdf_group, subrun_dir, ped_dir,
                                decoded_inner, hits_inner, combined_inner,
                                m3_track_inner, filtered_inner,
                                decode_exe, analyze_exe, combine_exe,
                                do_decode, do_analyze, do_combine,
                                do_m3_tracking, filter_by_m3,
                                m3_feu_num, tracking_sh_path, tracking_run_dir,
                                run_detectors, run_included, detector_info_dir,
                                save_fdfs, save_decoded, n_threads, cpp_env,
                                common_noise_subtraction
                            )
                            del prev_sizes[key]
                            found_new = True
                        else:
                            prev_sizes[key] = current

                if is_stale:
                    checked_stale_runs.add(run_dir.name)
                    print(f"[watcher] Marked stale (will skip): {run_dir.name}")

        if not found_new:
            print(f"[watcher] Sleeping {poll_interval}s...")
        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def _process_file_num(fnum, all_fdf_paths, subrun_dir, ped_dir,
                       decoded_inner, hits_inner, combined_inner,
                       m3_track_inner, filtered_inner,
                       decode_exe, analyze_exe, combine_exe,
                       do_decode, do_analyze, do_combine,
                       do_m3_tracking, filter_by_m3,
                       m3_feu_num, tracking_sh_path, tracking_run_dir,
                       detectors, included_detectors, detector_info_dir,
                       save_fdfs, save_decoded, n_threads, cpp_env,
                       common_noise_subtraction=True):

    decoded_dir  = subrun_dir / decoded_inner
    hits_dir     = subrun_dir / hits_inner
    combined_dir = subrun_dir / combined_inner
    m3_track_dir = subrun_dir / m3_track_inner
    filtered_dir = subrun_dir / filtered_inner

    m3_fdfs   = [p for p in all_fdf_paths if _get_feu_num_from_path(p) == m3_feu_num] if m3_feu_num is not None else []
    main_fdfs = [p for p in all_fdf_paths if _get_feu_num_from_path(p) != m3_feu_num] if m3_feu_num is not None else list(all_fdf_paths)

    # Step 1: M3 tracking
    if do_m3_tracking and m3_fdfs and not _m3_tracking_done(m3_track_dir, fnum):
        create_dir_if_not_exist(str(m3_track_dir))
        print(f"[m3_track] Running M3 tracking for file_num={fnum:03d}")
        _run_m3_tracking(m3_fdfs[0].parent, m3_track_dir,
                         tracking_sh_path, tracking_run_dir, m3_feu_num, fnum, cpp_env)

    # Step 2: Decode non-M3 FDFs
    if do_decode and main_fdfs:
        create_dir_if_not_exist(str(decoded_dir))
        tasks = []
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            for fdf in main_fdfs:
                root_path = decoded_dir / fdf.name.replace('.fdf', '.root')
                if root_path.exists():
                    continue
                tasks.append(pool.submit(_decode_file, str(fdf), str(root_path), decode_exe, cpp_env))
            for t in as_completed(tasks):
                t.result()

    # Step 3: M3 filtering (optional)
    if filter_by_m3 and _m3_tracking_done(m3_track_dir, fnum) and detectors and detector_info_dir:
        create_dir_if_not_exist(str(filtered_dir))
        _apply_m3_filter(fnum, m3_track_dir, decoded_dir, filtered_dir,
                         detectors, detector_info_dir, included_detectors)
        analyze_source_dir = filtered_dir
    else:
        analyze_source_dir = decoded_dir

    # Step 4: Analyze waveforms
    if do_analyze and main_fdfs:
        create_dir_if_not_exist(str(hits_dir))
        source_roots = [
            f for f in analyze_source_dir.glob('*.root')
            if '_datrun_' in f.name and _extract_file_num(f.name) == fnum
        ] if analyze_source_dir.exists() else []

        tasks = []
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            for root_path in source_roots:
                hits_path = hits_dir / root_path.name.replace('.root', '_hits.root')
                if hits_path.exists():
                    continue
                tasks.append(pool.submit(_analyze_file, str(root_path), ped_dir, str(hits_path), analyze_exe, cpp_env, common_noise_subtraction))
            for t in as_completed(tasks):
                t.result()

    # Step 5: Combine hits
    if do_combine and main_fdfs:
        create_dir_if_not_exist(str(combined_dir))
        feu_hits_map = _get_feu_hits_map(hits_dir, fnum)
        if feu_hits_map:
            combined_name = _make_combined_name(next(iter(feu_hits_map.values())))
            combined_path = combined_dir / combined_name
            if not combined_path.exists():
                _combine_hits(feu_hits_map, str(combined_path), combine_exe, cpp_env)

    # Step 6: Cleanup
    if not save_fdfs:
        for fdf in all_fdf_paths:
            if fdf.exists():
                fdf.unlink()
                print(f"[cleanup] Removed {fdf.name}")
    if not save_decoded:
        _remove_datrun_roots(decoded_dir, fnum)
        if filter_by_m3:
            _remove_datrun_roots(filtered_dir, fnum, label='filtered ')


def _decode_pedestals(ped_dir: str, decode_exe: str, cpp_env):
    """Decode pedestal FDFs in ped_dir in-place, skipping already-decoded ones."""
    ped_path = Path(ped_dir)
    if not ped_path.exists():
        return
    for fdf in ped_path.iterdir():
        if '_pedthr_' not in fdf.name or fdf.suffix != '.fdf':
            continue
        root_out = fdf.with_suffix('.root')
        if root_out.exists():
            continue
        print(f"[watcher] Decoding pedestal: {fdf.name}")
        _decode_file(str(fdf), str(root_out), decode_exe, cpp_env)


# ---------------------------------------------------------------------------
# M3 tracking
# ---------------------------------------------------------------------------

def _m3_tracking_done(m3_track_dir: Path, fnum: int) -> bool:
    if not m3_track_dir.exists():
        return False
    for f in m3_track_dir.iterdir():
        if f.name.endswith('_rays.root') and f'_{fnum:03d}_' in f.name:
            return True
    return False


def _run_m3_tracking(fdf_dir: Path, m3_track_dir: Path,
                     tracking_sh_path: str, tracking_run_dir: str,
                     m3_feu_num: int, fnum: int, cpp_env=None):
    """Run M3 tracking. The tracking binaries are ROOT-linked, so they run with
    cpp_env (the same ROOT-sourced environment used for decode/analyze/combine).
    Failures are caught and logged so a single bad file can't crash the watcher."""
    try:
        from m3_tracking_control import m3_tracking
    except ImportError:
        print("[m3_track] m3_tracking_control not available, skipping M3 tracking")
        return

    if not tracking_sh_path or not tracking_run_dir:
        print("[m3_track] tracking_sh_path or tracking_run_dir not configured, skipping")
        return

    try:
        m3_tracking(str(fdf_dir) + '/', tracking_sh_path, tracking_run_dir,
                    out_dir=str(m3_track_dir) + '/', m3_feu_num=m3_feu_num, file_num=fnum, env=cpp_env)
    except Exception as e:
        print(f"[m3_track] ERROR: M3 tracking failed for file_num={fnum:03d}: {e}\n"
              f"[m3_track] Skipping M3 tracking for this file and continuing.")


# ---------------------------------------------------------------------------
# M3 filtering
# ---------------------------------------------------------------------------

def _apply_m3_filter(fnum: int, m3_track_dir: Path, decoded_dir: Path, filtered_dir: Path,
                     detectors: list, detector_info_dir: str, included_detectors):
    try:
        from m3_filter import filter_decoded_by_m3
    except ImportError:
        print("[m3_filter] m3_filter module not available, skipping M3 filtering")
        return

    print(f"[m3_filter] Filtering file_num={fnum:03d} by M3 tracking")
    filter_decoded_by_m3(
        str(filtered_dir) + '/',
        str(m3_track_dir) + '/',
        str(decoded_dir) + '/',
        detectors, detector_info_dir, included_detectors,
        file_num=fnum
    )


# ---------------------------------------------------------------------------
# Stale-run detection
# ---------------------------------------------------------------------------

def _run_is_stale(run_dir: Path, raw_inner: str, stale_days: float) -> bool:
    cutoff = time.time() - stale_days * 86400
    newest_mtime = 0.0
    for subrun_dir in run_dir.iterdir():
        if not subrun_dir.is_dir():
            continue
        raw_dir = subrun_dir / raw_inner
        if raw_dir.exists():
            mtime = raw_dir.stat().st_mtime
            if mtime > newest_mtime:
                newest_mtime = mtime
    # A brand-new run whose raw_daq_data dir doesn't exist yet leaves newest_mtime
    # at 0.0; don't mark it stale (0.0 < cutoff is always True) or it gets added to
    # checked_stale_runs permanently and its data is never processed once it arrives.
    if newest_mtime == 0.0:
        return False
    return newest_mtime < cutoff


# ---------------------------------------------------------------------------
# Directory / filename helpers
# ---------------------------------------------------------------------------

def _resolve_pedestal_dir(raw_dir: Path, pedestal_loc: str, pedestal_base_dir: str) -> str:
    if pedestal_loc == 'same':
        return str(raw_dir)
    if pedestal_loc == 'abs':
        return pedestal_base_dir
    if pedestal_loc == 'find':
        txt = raw_dir / 'pedestal_run.txt'
        if txt.exists():
            ped_run = txt.read_text().strip()
            return str(Path(pedestal_base_dir) / ped_run / 'pedestals')
        print(f"[watcher] pedestal_run.txt not found in {raw_dir}, skipping pedestal decode")
    return ''


def _get_data_file_nums(raw_dir: Path) -> set:
    nums = set()
    for f in raw_dir.iterdir():
        if f.suffix == '.fdf' and '_datrun_' in f.name:
            n = _extract_file_num(f.name)
            if n is not None:
                nums.add(n)
    return nums


def _get_processed_file_nums(subrun_dir, combined_inner, hits_inner, decoded_inner, filtered_inner,
                              m3_track_inner, do_combine, do_analyze, filter_by_m3, do_m3_tracking,
                              m3_feu_num) -> set:
    """Return file_nums whose final pipeline output already exists.

    When M3 tracking is enabled, a file_num only counts as done once its
    _rays.root also exists.  Otherwise a file_num whose M3 pass failed or was
    skipped would still be marked complete by the main pipeline's combined
    output and never retried, silently dropping M3 rays for that file_num."""
    if do_combine:
        check_dir, flag = subrun_dir / combined_inner, 'feu-combined'
    elif do_analyze:
        check_dir, flag = subrun_dir / hits_inner, '_hits'
    elif filter_by_m3:
        check_dir, flag = subrun_dir / filtered_inner, '_filtered'
    else:
        check_dir, flag = subrun_dir / decoded_inner, '.root'

    done = set()
    if check_dir.exists():
        for f in check_dir.iterdir():
            if flag not in f.name:
                continue
            n = _extract_file_num(f.name)
            if n is not None:
                done.add(n)

    if do_m3_tracking and m3_feu_num is not None:
        done &= _get_m3_done_file_nums(subrun_dir / m3_track_inner)

    return done


def _get_m3_done_file_nums(m3_track_dir: Path) -> set:
    """Return file_nums that already have an M3 _rays.root output."""
    done = set()
    if not m3_track_dir.exists():
        return done
    for f in m3_track_dir.iterdir():
        if f.name.endswith('_rays.root'):
            n = _extract_file_num(f.name)
            if n is not None:
                done.add(n)
    return done


def _load_detector_info_from_run(run_dir: Path):
    """Load detectors and included_detectors from the run's run_config.json, if it exists."""
    cfg_path = run_dir / 'run_config.json'
    if not cfg_path.exists():
        return None, None
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        return cfg.get('detectors'), cfg.get('included_detectors')
    except Exception as e:
        print(f"[watcher] Could not load run_config.json from {run_dir}: {e}")
        return None, None


def _get_feu_num_from_path(fdf_path: Path) -> int:
    """Extract the 2-digit FEU number from a FDF filename."""
    m = re.search(r'_(\d{3})_(\d{2})[._]', fdf_path.name)
    if m:
        return int(m.group(2))
    return -1


def _get_feu_hits_map(hits_dir: Path, fnum: int) -> dict:
    """Return {feu_num: path_str} for all hits files matching fnum."""
    result = {}
    if not hits_dir.exists():
        return result
    for f in hits_dir.iterdir():
        m = re.match(r'.*_(\d{3})_(\d{2})_hits\.root$', f.name)
        if m and int(m.group(1)) == fnum:
            result[int(m.group(2))] = str(f)
    return result


def _extract_file_num(filename: str):
    """Extract the 3-digit file-number from a DREAM filename, or None."""
    m = re.match(r'.*_(\d{3})_feu-combined', filename)
    if m:
        return int(m.group(1))
    m = re.match(r'.*_(\d{3})_rays\.root$', filename)
    if m:
        return int(m.group(1))
    m = re.match(r'.*_(\d{3})_(\d{2})[._]', filename)
    if m:
        return int(m.group(1))
    return None


def _make_combined_name(a_hits_path: str) -> str:
    """Replace the 2-digit FEU field with 'feu-combined' in a hits filename."""
    name = os.path.basename(a_hits_path)
    return re.sub(r'(_\d{3}_)\d{2}(_hits\.root)$', r'\1feu-combined\2', name)


def _remove_datrun_roots(directory: Path, fnum: int, label: str = ''):
    """Delete decoded/filtered datrun ROOT files for fnum in directory."""
    if not directory.exists():
        return
    for f in directory.glob('*.root'):
        if '_datrun_' in f.name and _extract_file_num(f.name) == fnum:
            f.unlink()
            print(f"[cleanup] Removed {label}{f.name}")


# ---------------------------------------------------------------------------
# Worker functions (invoke C++ executables)
# ---------------------------------------------------------------------------

def _decode_file(fdf_path: str, root_path: str, decode_exe: str, cpp_env):
    print(f"[decode]  {os.path.basename(fdf_path)}")
    subprocess.run([decode_exe, fdf_path, root_path], env=cpp_env)


def _analyze_file(root_path: str, ped_dir: str, hits_out_path: str, analyze_exe: str, cpp_env,
                  common_noise_subtraction: bool = True):
    # anchored to the tail: run names like det3_420_820 must not match
    feu_match = re.search(r'_(\d{3})_(\d{2})\.root$', os.path.basename(root_path))
    if not feu_match:
        print(f"[analyze] Cannot extract FEU number from {root_path}, skipping")
        return
    feu_num = int(feu_match.group(2))

    ped_path = ''
    if ped_dir and os.path.isdir(ped_dir):
        for f in os.listdir(ped_dir):
            m = re.search(r'_(\d{3})_(\d{2})\.root$', f)
            if m and int(m.group(2)) == feu_num and '_pedthr_' in f and f.endswith('.root'):
                ped_path = os.path.join(ped_dir, f)
                break

    print(f"[analyze] {os.path.basename(root_path)}")
    cmd = [analyze_exe, root_path, hits_out_path, ped_path, '--cns', '1' if common_noise_subtraction else '0']
    subprocess.run(cmd, env=cpp_env)


def _combine_hits(feu_hits_map: dict, combined_path: str, combine_exe: str, cpp_env):
    print(f"[combine] -> {os.path.basename(combined_path)}")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=True) as tmp:
        for feu, path in sorted(feu_hits_map.items()):
            tmp.write(f"{path} {feu}\n")
        tmp.flush()
        subprocess.run([combine_exe, tmp.name, combined_path], check=True, env=cpp_env)


# ---------------------------------------------------------------------------
# Startup binary check
# ---------------------------------------------------------------------------

def _check_binaries(do_decode, decode_exe, do_analyze, analyze_exe,
                    do_combine, combine_exe, do_m3_tracking, tracking_sh_path):
    checks = [
        (do_decode,      decode_exe,       "decode",             "mm_dream_reconstruction/build/decoder/decode"),
        (do_analyze,     analyze_exe,      "analyze_waveforms",  "mm_dream_reconstruction/build/waveform_analysis/analyze_waveforms"),
        (do_combine,     combine_exe,      "combine_feus_hits",  "mm_dream_reconstruction/build/feu_hit_combiner/combine_feus_hits"),
        (do_m3_tracking, tracking_sh_path, "run_tracking_single.sh", "cosmic_bench_m3_tracking/run_tracking_single.sh"),
    ]
    warned = False
    for enabled, path, name, hint in checks:
        if not enabled:
            continue
        if not path:
            print(f"[watcher] WARNING: {name} is enabled but no path configured")
            warned = True
        elif not os.path.isfile(path):
            print(f"[watcher] WARNING: {name} binary not found: {path}")
            print(f"[watcher]          Expected at: {hint}  — has it been built?")
            warned = True
    if warned:
        print("[watcher] WARNING: Missing binaries listed above — affected pipeline steps will fail when reached.")


# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------

def _build_cpp_env(setup_script: str):
    """Source setup_script in a login bash shell and return the resulting env dict.

    Uses 'env -0' (null-byte-separated) so env vars with newlines in their
    values don't corrupt the parse (e.g. LS_COLORS, BASH_FUNC_*, etc.).
    Returns None and falls back to the process default env if sourcing fails.
    """
    result = subprocess.run(
        ['bash', '-l', '-c', f'{setup_script} && env -0'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[watcher] WARNING: cpp_setup_script exited {result.returncode}:\n{result.stderr[:400]}")
    env = {}
    for entry in result.stdout.split('\0'):
        if '=' in entry:
            k, _, v = entry.partition('=')
            env[k] = v
    if not env:
        print("[watcher] WARNING: _build_cpp_env produced empty env, using process default")
        return None
    return env


if __name__ == '__main__':
    main()
