#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on April 29 9:37 PM 2024
Created in PyCharm
Created as Cosmic_Bench_DAQ_Control/run_config_template.py

@author: Dylan Neff, Dylan
"""

import json
import copy

# ---------------------------------------------------------------------------
# Site configuration — edit here or use the Flask GUI to switch projects
# ---------------------------------------------------------------------------
BASE_DISK     = '/mnt/cosmic_data/'
PROJECT       = 'P2'  # 'MX17', 'P2', 'clas12', 'EIC'
BASE_DATA_DIR = f'{BASE_DISK}{PROJECT}/'


class Config:
    def __init__(self):
        # self.run_name = 'mx17_det4_ArIso_HV_Scan_5-7-26'
        # self.run_name = 'zs_compression_test_M3_6-7-26'
        # self.run_name = 'mx17_det3_new_test_zs_m3_6-17-26'
        # self.run_name = 'mx17_det2_det3_weekend_6-20-26'
        # self.run_name = 'mx17_det2_det3_overnight_6-22-26'
        # self.run_name = 'mx17_det3_day_6-25-26'
        # self.run_name = 'P2_det1-6-25-26_test'
        # self.run_name = 'mx17_det6_det7_overnight_6-26-26'
        # self.run_name = 'mx17_det6_det7_hv_scan_6-26-26'
        # self.run_name = 'mx17_det3_saturday_scan_6-27-26'
        # self.run_name = 'p2_det1_long_run_6-30-26'
        # self.run_name = 'p2_det1_mesh_hv_scan_7-2-26'
        # self.run_name = 'p2_det1_long_run_7-4-26'
        # self.run_name = 'p2_det1_long_run_7-7-26'
        # self.run_name = 'p2_det1_det2_long_run_mesh_scan_7-9-26'
        # self.run_name = 'p2_det3_det4_long_run_drift_mesh_scan_7-15-26'
        # self.run_name = 'p2_det4_long_run_drift_mesh_scan_7-15-26'
        # self.run_name = 'p2_det3_det4_drift_scan_7-16-26'
        # self.run_name = 'p2_det3_mesh_scan_det4_initial_7-16-26'
        # self.run_name = 'p2_det1_long_run_mesh_scan_7-19-26'
        self.run_name = 'p2_det1_drift_scan_7-19-26'
        # self.data_out_dir = '/mnt/cosmic_data/Run/'
        # self.data_out_dir = '/data/cosmic_data/Run_MX/'
        self.base_out_dir = BASE_DATA_DIR
        self.data_out_dir = f'{self.base_out_dir}Run/'
        self.run_out_dir = f'{self.data_out_dir}{self.run_name}/'
        self.raw_daq_inner_dir = 'raw_daq_data'
        self.decoded_root_inner_dir = 'decoded_root'
        self.filtered_root_inner_dir = 'filtered_root'
        self.m3_tracking_inner_dir = 'm3_tracking_root'
        self.detector_info_dir = f'/mnt/cosmic_data/config/detectors/'
        self.m3_feu_num = 1
        self.power_off_hv_at_end = True  # True to power off HV at end of run
        self.save_fdfs = True  # True to save FDF files after processing
        self.resume = True  # True to skip sub-runs already completed in run_out_dir (resume after a crash).
        # Completion is tracked by a '.subrun_complete' marker written into each sub-run's out dir on success,
        # so the full sub_runs list (and thus run_config.json) stays intact while only unfinished sub-runs run.
        self.start_time = None  # '2024-06-03 15:30:00'  # 'YYYY-MM-DD HH:MM:SS' or None to start immediately
        self.write_all_dectors_to_json = False  # Only when making run config json template.
        self.gas = 'Ar/Iso 95/5'  # Gas type for run
        # self.gas = 'Ar/CO2/Iso 93/5/2'  # Gas type for run
        # self.gas = 'Helium/Ethane 96.5/3.5'  # Gas type for run
        # self.gas = 'Ar/CF4 90/10'  # Gas type for run

        self.dream_daq_info = {
            # 'ip': '192.168.10.100',
            'ip': '192.168.10.1',
            'port': 1101,
            # 'daq_config_template_path': '/mnt/cosmic_data/clas12/dream_config/CosmicTb_clas12.cfg',
            # 'daq_config_template_path': '/mnt/cosmic_data/MX17/dream_config/CosmicTb_MX17_ZS_scan.cfg',
            # 'daq_config_template_path': '/mnt/cosmic_data/MX17/dream_config/CosmicTb_MX17.cfg',
            # 'daq_config_template_path': '/mnt/cosmic_data/P2/dream_config/CosmicTb_P2.cfg',
            'run_directory': f'{self.base_out_dir}dream_run/{self.run_name}/',
            # 'data_out_dir': f'/mnt/cosmic_data/Run/{self.run_name}',
            'data_out_dir': self.run_out_dir,
            'raw_daq_inner_dir': self.raw_daq_inner_dir,
            'copy_on_fly': True,  # True to copy raw data to out dir during run, False to copy after run
            'n_samples_per_waveform': 32,  # Number of samples per waveform to configure in DAQ
            'zero_suppress': False,  # True to run in zero suppression mode, False to run in full readout mode
            'pedestals_dir': f'{self.base_out_dir}pedestals/',  # None to ignore, else top directory for pedestal runs
            'pedestals': 'latest',
            # 'latest' for most recent, otherwise specify directory name, eg "pedestals_10-22-25_13-43-34"
            # 'latency': 33,  # Latency setting for DAQ in clock cycles
            # 'latency': 22,  # Latency setting for DAQ in clock cycles
            'sample_period': 60,  # ns, sampling period
            'zs_check_sample': 1,  # Number of samples to read out beyond threshold crossing
            # 'zs_check_sample': 4,  # Number of samples to read out beyond threshold crossing
            'pedestal_subtraction': False,
            'common_noise_subtraction': False,
            'zs_type': 'tpc',
            # Off: use the dedicated 'latest' pedestals copied in by get_pedestals instead of
            # taking a per-subrun pedestal run. (Both at once = two _pedthr_ sets per FEU in
            # raw_daq_data -> processor refuses with "Multiple pedestals for FEU".)
            # 7-15-26: off — take a dedicated pedestal run at 200 V mesh/drift first
            # (run_config_pedestals.py), which every subrun then reuses via 'latest'.
            'do_pedestal_threshold_run': False,  # Sys Action PedThrRun (bool/int/str → 0 or 1)
            'do_trigger_threshold_run': False,   # Sys Action TrgThrRun
            'do_data_run': True,                 # Sys Action DataRun
            # True to auto-select the active FEUs in the .cfg from the included detectors' dream_feus maps.
            # Only the Sys Topo / Feu_RunCtrl_Id / NetChan_Ip lines for FEUs actually used by the included
            # detectors are left active; the rest are commented out. The template stays the source of truth
            # for each FEU's role (Trg/Dat) and hardware Id/IP.
            'set_feus_from_detectors': True,
        }
        if PROJECT == 'MX17':
            self.dream_daq_info['daq_config_template_path'] = '/mnt/cosmic_data/MX17/dream_config/CosmicTb_MX17.cfg'
        elif PROJECT == 'P2':
            self.dream_daq_info['daq_config_template_path'] = '/mnt/cosmic_data/P2/dream_config/CosmicTb_P2.cfg'

        self.hv_control_info = {
            'ip': '192.168.10.1',
            'port': 1100,
        }

        self.hv_info = {
            'ip': '192.168.10.81',
            'username': 'admin',
            'password': 'admin',
            'n_cards': 4,
            'n_channels_per_card': 12,
            'run_out_dir': self.run_out_dir,
            'hv_monitoring': True,  # True to monitor HV during run, False to not monitor
            'monitor_interval': 0.5,  # Seconds between HV monitoring reads (sub-second OK; ~0.1s query overhead/cycle)
        }


        self.sub_runs = []  # Append subruns in order they should be run.

        # det3 (mx17_3) on P2 (upper): drift (0, 7), resist (3, 4).
        # M3 telescope: drift 0:8-11 @ 500V, mesh 3:8-11 @ 455V (FEU 1 = trigger).
        default_drift, default_resist = 1000, 490  # V

        # ---------------------------------------------------------------------
        # P2_1 drift scan, 7-19-26 (det1 on p2_z; det4 on p1_z is DEAD —
        # excluded from the readout (FEUs 3/4 off) and its HV channels held at
        # 0 the whole run):
        #   Drift HV scan at fixed mesh = 415 V: step the drift up in 50 V
        #   intervals, 30 min subruns, 12 points (6 h): drift 415 -> 965 V.
        #   Start at 0 drift-gap potential (drift = mesh = 415 V) and increase
        #   the gap by 50 V each point — the potential across the drift gap is
        #   drift - mesh, so it grows 0 -> 550 V.
        # Total: 6 h, HV powered off automatically at the end
        # (power_off_hv_at_end).
        # Pedestals: same FEU set (1, 6, 7) as the 7-19-26 mesh-scan run — if
        # that run's dedicated 200 V pedestal (pedestals_07-19-26_00-21-00) is
        # still current (no FEU-set or hardware change), 'latest' reuses it and
        # no new pedestal run is needed; otherwise take a fresh one first via
        # run_config_pedestals.py.
        # M3 telescope (cards 0/3 ch 8-11, drift 500 / mesh 455) held at its
        # usual operating point throughout.
        # P2_1 HV: mesh (1, 2), drift (1, 3) — on the p2-shelf HV cables.
        # P2_4 HV: mesh (1, 0), drift (1, 1) — held at 0 (dead detector).
        det1_mesh_fixed = 415  # V, P2_1 mesh held fixed for the drift scan

        def p2_hvs(det1_mesh, det1_drift):
            """P2_4 channels fixed at 0 -> hv_control powers them off (det4 dead)."""
            return {
                0: {
                    8: 500,  # M3
                    9: 500,  # M3
                    10: 500,  # M3
                    11: 500,  # M3
                },
                1: {
                    0: 0,           # P2_4 mesh — dead, off
                    1: 0,           # P2_4 drift — dead, off
                    2: det1_mesh,   # P2_1 mesh
                    3: det1_drift,  # P2_1 drift
                },
                3: {
                    8: 455,  # M3
                    9: 455,  # M3
                    10: 455,  # M3
                    11: 455,  # M3
                },
            }

        for step in range(12):  # 12 x 30 min = 6 h drift scan, mesh fixed at 415 V
            det1_drift = det1_mesh_fixed + 50 * step  # 415 -> 965 V; drift gap 0 -> 550 V
            new_subrun = {
                'sub_run_name': f'drift_scan_det1_{det1_mesh_fixed}_{det1_drift}',
                'run_time': 30,  # Minutes
                'hvs': p2_hvs(det1_mesh_fixed, det1_drift),
            }
            self.sub_runs.append(new_subrun)


        # new_subrun = {
        #     'sub_run_name': f'initial_run',
        #     'run_time': 8 * 60,  # Minutes
        #     'hvs': {
        #         0: {
        #             7: 900,
        #             8: 500,
        #             9: 500,
        #             10: 500,
        #             11: 500,
        #         },
        #         3: {
        #             0: 500,
        #             8: 455,
        #             9: 455,
        #             10: 455,
        #             11: 455,
        #         }
        #     },
        #     'daq_config_template_path': '/mnt/cosmic_data/MX17/dream_config/CosmicTb_MX17.cfg',
        #     'pedestals_dir': f'{self.base_out_dir}pedestals/',
        #     'zero_suppress': False,
        #     'common_noise_subtraction': False,
        # },
        # self.sub_runs.append(new_subrun)

        # new_subrun = {
        #     'sub_run_name': 'no_zs',
        #     'run_time': 10,  # Minutes
        #     'hvs': {
        #         0: {
        #             7: 900,
        #             8: 500,
        #             9: 500,
        #             10: 500,
        #             11: 500,
        #         },
        #         3: {
        #             0: 500,
        #             8: 455,
        #             9: 455,
        #             10: 455,
        #             11: 455,
        #         }
        #     },
        #     'zero_suppress': False,
        #     'pedestals': 'pedestals_290'
        # },
        # self.sub_runs.append(new_subrun)
        #
        # new_subrun = {
        #     'sub_run_name': 'zs_type_tracker',
        #     'run_time': 10,  # Minutes
        #     'hvs': {
        #         0: {
        #             7: 900,
        #             8: 500,
        #             9: 500,
        #             10: 500,
        #             11: 500,
        #         },
        #         3: {
        #             0: 500,
        #             8: 455,
        #             9: 455,
        #             10: 455,
        #             11: 455,
        #         }
        #     },
        #     'pedestals': 'pedestals_290',
        #     'zs_type': 'tracker',
        # },
        # self.sub_runs.append(new_subrun)
        #
        # new_subrun = {
        #     'sub_run_name': 'long_run',
        #     'run_time': 24 * 60,  # Minutes
        #     'hvs': {
        #         0: {
        #             7: 900,
        #             8: 500,
        #             9: 500,
        #             10: 500,
        #             11: 500,
        #         },
        #         3: {
        #             0: 510,
        #             8: 455,
        #             9: 455,
        #             10: 455,
        #             11: 455,
        #         }
        #     }
        # },
        # self.sub_runs.append(new_subrun)

        # drifts = [900]
        # for drift in drifts:
        #     resists = [530, 520, 500, 490, 480, 470, 460, 450, 440, 510]
        #     for resist in resists:
        #         # time = 6.5 * 60 if resist == 510 else 45
        #         time = 5
        #         new_subrun = {
        #             'sub_run_name': f'resist_{resist}V_drift_{drift}V',
        #             'run_time': time,  # Minutes
        #             'hvs': {
        #                 0: {
        #                     7: drift,
        #                     8: 500,
        #                     9: 500,
        #                     10: 500,
        #                     11: 500,
        #                 },
        #                 3: {
        #                     0: resist,
        #                     8: 455,
        #                     9: 455,
        #                     10: 455,
        #                     11: 455,
        #                 },
        #             }
        #         }
        #         self.sub_runs.append(new_subrun)

        #
        # drift, resist = 800, 505
        # new_subrun = {
        #     'sub_run_name': f'final_resist_{resist}V_drift_{drift}V',
        #     'run_time': 24 * 60,  # Minutes
        #     'hvs': {
        #         0: {
        #             7: drift,
        #             8: 500,
        #             9: 500,
        #             10: 500,
        #             11: 500,
        #         },
        #         3: {
        #             0: resist,
        #             8: 455,
        #             9: 455,
        #             10: 455,
        #             11: 455,
        #         },
        #     }
        # }
        # self.sub_runs.append(new_subrun)

        # check_samples = [0, 1, 2, 3, 4]
        # for check_sample in check_samples:
        #     new_subrun = {
        #         'sub_run_name': f'zs_type_tpc_{check_sample}_sample',
        #         'run_time': 10,  # Minutes
        #         'hvs': {
        #             0: {
        #                 7: 900,
        #                 8: 500,
        #                 9: 500,
        #                 10: 500,
        #                 11: 500,
        #             },
        #             3: {
        #                 0: 500,
        #                 8: 455,
        #                 9: 455,
        #                 10: 455,
        #                 11: 455,
        #             }
        #         },
        #         'pedestals': 'pedestals_290',
        #         'zs_type': 'tpc',
        #         'zs_check_sample': check_sample,
        #     }
        #     self.sub_runs.append(new_subrun)
        #
        # peds = [290, 300, 310, 330, 340, 350, 400, 450, 500, 550, 600, 700, 800, 900, 1000, 320]
        # for ped in peds:
        #     new_subrun = {
        #         'sub_run_name': f'ped_{ped}',
        #         'run_time': 15,  # Minutes
        #         'hvs': {
        #             0: {
        #                 7: 900,
        #                 8: 500,
        #                 9: 500,
        #                 10: 500,
        #                 11: 500,
        #             },
        #             3: {
        #                 0: 500,
        #                 8: 455,
        #                 9: 455,
        #                 10: 455,
        #                 11: 455,
        #             }
        #         },
        #         'pedestals': f'pedestals_{ped}',
        #         'zs_type': 'tpc',
        #         'zs_check_sample': 1,
        #     }
        #     self.sub_runs.append(new_subrun)

        # new_subrun = {
        #     'sub_run_name': f'final_run',
        #     'run_time': 8 * 60,  # Minutes
        #     'hvs': {
        #         0: {
        #             7: 900,
        #             8: 500,
        #             9: 500,
        #             10: 500,
        #             11: 500,
        #         },
        #         3: {
        #             0: 500,
        #             8: 455,
        #             9: 455,
        #             10: 455,
        #             11: 455,
        #         }
        #     },
        #     'daq_config_template_path': '/mnt/cosmic_data/MX17/dream_config/CosmicTb_MX17.cfg',
        #     'pedestals_dir': f'{self.base_out_dir}pedestals/',
        #     'zero_suppress': False,
        #     'common_noise_subtraction': False,
        # }
        # self.sub_runs.append(new_subrun)


        self.bench_geometry = {
            'p1_z': 227,  # mm  To the top of P1 from the top of PB
            'p2_z': 697,  # mm  To the top of P1 from the top of PB
            'bottom_level_z': 82,  # mm  From the top of P1 to the bottom level of stand
            'level_z_spacing': 97,  # mm  Spacing between levels on stand
            'board_thickness': 5,  # mm  Thickness of PCB for test boards  Guess!
            'banco_arm_bottom_to_center': (193 - 172) / 2,  # mm from bottom of lower banco arm to center of banco arm
            'banco_arm_separation_z': 172 - 41,  # mm from bottom of lower banco arm to bottom of upper banco arm
            'banco_arm_right_y': 34 + 100,  # mm from center of banco to right edge of banco arm
            'banco_arm_length_y': 230,  # mm from left edge of banco arm to right edge of banco arm
        }

        # self.included_detectors = ['banco_ladder160', 'banco_ladder163', 'banco_ladder157', 'banco_ladder162',
        #                            'urw_strip', 'urw_inter', 'asacusa_strip_1', 'asacusa_strip_2', 'strip_plein_1',
        #                            'strip_strip_1',
        #                            'm3_bot_bot', 'm3_bot_top', 'm3_top_bot', 'm3_top_top', 'scintillator_top']
        # self.included_detectors = ['mx17_3', 'P2_1',
                                #    'm3_bot_bot', 'm3_bot_top', 'm3_top_bot', 'm3_top_top']
        # self.included_detectors = ['P2_1', 'P2_2',
        #                            'm3_bot_bot', 'm3_bot_top', 'm3_top_bot', 'm3_top_top']
        # self.included_detectors = ['P2_3', 'P2_4',
        #                            'm3_bot_bot', 'm3_bot_top', 'm3_top_bot', 'm3_top_top']
        # P2_4 (FEUs 3/4) is dead — excluded from the readout entirely; its HV
        # channels are held at 0 in every subrun's hvs map.
        self.included_detectors = ['P2_1',
                                   'm3_bot_bot', 'm3_bot_top', 'm3_top_bot', 'm3_top_top']
        # self.included_detectors = ['clas12_test',
        #                                    'm3_bot_bot', 'm3_bot_top', 'm3_top_bot', 'm3_top_top']

        self.detectors = [
            {
                'name': 'P2_1',
                'description': 'Bulked at 11-6-26  with footprint on the mesh from the frame gluing',
                'det_type': 'P2',
                'resist_type': 'none',
                'bulked_from': 'Alex+Arnaud',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p2_z'] + self.bench_geometry['board_thickness'],  # mm  moved to p2 shelf 7-19-26
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                # On the p2-shelf HV cables since 7-19-26 (was (1, 0)/(1, 1) on the p1 shelf).
                'hv_channels': {
                    'drift': (1, 3),
                    'mesh': (1, 2),
                },
                # Recabled 7-19-26 on the p2 shelf: connectors 1 and 10 disconnected,
                # connectors 2-9 go incrementally to FEU 6 (1-8) then FEU 7 (1-8).
                'dream_feus': {
                    # 'c_1_bot': None,  # connector 1 disconnected
                    # 'c_1_top': None,
                    'c_2_bot': (6, 1),  # Runs along x direction, indicates y hit location
                    'c_2_top': (6, 2),
                    'c_3_bot': (6, 3),
                    'c_3_top': (6, 4),
                    'c_4_bot': (6, 5),
                    'c_4_top': (6, 6),
                    'c_5_bot': (6, 7),  # Runs along y direction, indicates x hit location
                    'c_5_top': (6, 8),
                    'c_6_bot': (7, 1),
                    'c_6_top': (7, 2),
                    'c_7_bot': (7, 3),
                    'c_7_top': (7, 4),
                    'c_8_bot': (7, 5),
                    'c_8_top': (7, 6),
                    'c_9_bot': (7, 7),
                    'c_9_top': (7, 8),
                    # 'c_10_bot': None,  # connector 10 disconnected
                    # 'c_10_top': None,
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'c_2_bot': 'rotated_inverted',
                    'c_2_top': 'rotated_inverted',
                    'c_3_bot': 'rotated_inverted',
                    'c_3_top': 'rotated_inverted',
                    'c_4_bot': 'rotated_inverted',
                    'c_4_top': 'rotated_inverted',
                    'c_5_bot': 'rotated_inverted',
                    'c_5_top': 'rotated_inverted',
                    'c_6_bot': 'rotated_inverted',
                    'c_6_top': 'rotated_inverted',
                    'c_7_bot': 'rotated_inverted',
                    'c_7_top': 'rotated_inverted',
                    'c_8_bot': 'rotated_inverted',
                    'c_8_top': 'rotated_inverted',
                    'c_9_bot': 'rotated_inverted',
                    'c_9_top': 'rotated_inverted',
                },
            },
            {
                'name': 'P2_2',
                'description': 'Bulked at 25-6-26 with misaligned wall',
                'det_type': 'P2',
                'resist_type': 'none',
                'bulked_from': 'Alex+Enzo',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p2_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (1, 3),
                    'mesh': (1, 2),
                },
                # Physical cabling deduced from track-hit correlation on the 7-9-26 run
                # (hit-level Procrustes fit: scale 0.92, median residual 11 mm; wrong
                # starts give scale ~0.25 / ~100 mm):
                #   - connector 1 is DISCONNECTED from the detector (no readout);
                #   - connectors 2-7 go incrementally to FEU 6 (5-8) then FEU 7 (1-8);
                #   - connectors 8-10 continue on FEU 8, excluded from runs for now
                #     (crashes the DAQ), so they are commented out.
                'dream_feus': {
                    # 'c_1_bot': None,  # connector 1 disconnected from detector
                    # 'c_1_top': None,
                    'c_2_bot': (6, 5),
                    'c_2_top': (6, 6),
                    'c_3_bot': (6, 7),
                    'c_3_top': (6, 8),
                    'c_4_bot': (7, 1),
                    'c_4_top': (7, 2),
                    'c_5_bot': (7, 3),
                    'c_5_top': (7, 4),
                    'c_6_bot': (7, 5),
                    'c_6_top': (7, 6),
                    'c_7_bot': (7, 7),
                    'c_7_top': (7, 8),
                    # 'c_8_bot': (8, 1),  # FEU 8 excluded from run
                    # 'c_8_top': (8, 2),
                    # 'c_9_bot': (8, 3),
                    # 'c_9_top': (8, 4),
                    # 'c_10_bot': (8, 5),
                    # 'c_10_top': (8, 6),
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'c_2_bot': 'rotated_inverted',
                    'c_2_top': 'rotated_inverted',
                    'c_3_bot': 'rotated_inverted',
                    'c_3_top': 'rotated_inverted',
                    'c_4_bot': 'rotated_inverted',
                    'c_4_top': 'rotated_inverted',
                    'c_5_bot': 'rotated_inverted',
                    'c_5_top': 'rotated_inverted',
                    'c_6_bot': 'rotated_inverted',
                    'c_6_top': 'rotated_inverted',
                    'c_7_bot': 'rotated_inverted',
                    'c_7_top': 'rotated_inverted',
                    # 'c_8_bot': 'rotated_inverted',  # FEU 8 excluded from run
                    # 'c_8_top': 'rotated_inverted',
                    # 'c_9_bot': 'rotated_inverted',
                    # 'c_9_top': 'rotated_inverted',
                    # 'c_10_bot': 'rotated_inverted',
                    # 'c_10_top': 'rotated_inverted',
                },
            },
            {
                'name': 'P2_3',
                'description': 'Bulked at 25-6-26 by Alex+Enzo. Mesh wall insulation cured 2 x 10 min '
                               '(half of the lamps available for each cure).',
                'det_type': 'P2',
                'resist_type': 'none',
                'bulked_from': 'Alex+Enzo',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p2_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (1, 3),
                    'mesh': (1, 2),
                },
                # Connectors 1 and 10 disconnected from the detector; connectors 8 and 9
                # additionally disconnected 7-16-26. Connectors 2-7 go incrementally to
                # FEU 6 (1-8) then FEU 7 (1-4).
                'dream_feus': {
                    # 'c_1_bot': None,  # connector 1 disconnected from detector
                    # 'c_1_top': None,
                    'c_2_bot': (6, 1),  # Runs along x direction, indicates y hit location
                    'c_2_top': (6, 2),
                    'c_3_bot': (6, 3),
                    'c_3_top': (6, 4),
                    'c_4_bot': (6, 5),
                    'c_4_top': (6, 6),
                    'c_5_bot': (6, 7),  # Runs along y direction, indicates x hit location
                    'c_5_top': (6, 8),
                    'c_6_bot': (7, 1),
                    'c_6_top': (7, 2),
                    'c_7_bot': (7, 3),
                    'c_7_top': (7, 4),
                    # 'c_8_bot': (7, 5),  # connector 8 disconnected from detector 7-16-26
                    # 'c_8_top': (7, 6),
                    # 'c_9_bot': (7, 7),  # connector 9 disconnected from detector 7-16-26
                    # 'c_9_top': (7, 8),
                    # 'c_10_bot': None,  # connector 10 disconnected from detector
                    # 'c_10_top': None,
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'c_2_bot': 'rotated_inverted',
                    'c_2_top': 'rotated_inverted',
                    'c_3_bot': 'rotated_inverted',
                    'c_3_top': 'rotated_inverted',
                    'c_4_bot': 'rotated_inverted',
                    'c_4_top': 'rotated_inverted',
                    'c_5_bot': 'rotated_inverted',
                    'c_5_top': 'rotated_inverted',
                    'c_6_bot': 'rotated_inverted',
                    'c_6_top': 'rotated_inverted',
                    'c_7_bot': 'rotated_inverted',
                    'c_7_top': 'rotated_inverted',
                    # 'c_8_bot': 'rotated_inverted',  # connector 8 disconnected 7-16-26
                    # 'c_8_top': 'rotated_inverted',
                    # 'c_9_bot': 'rotated_inverted',  # connector 9 disconnected 7-16-26
                    # 'c_9_top': 'rotated_inverted',
                },
            },
            {
                'name': 'P2_4',
                'description': 'Bulked at 8-7-26 by Alex+Enzo. First bulking with the cleanest evac line.',
                'det_type': 'P2',
                'resist_type': 'none',
                'bulked_from': 'Alex+Enzo',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p1_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (1, 1),
                    'mesh': (1, 0),
                },
                # Connectors 1 and 10 disconnected from the detector; connector 2
                # additionally disconnected 7-16-26. Connectors 3-9 go incrementally to
                # FEU 3 (3-8) then FEU 4 (1-8).
                'dream_feus': {
                    # 'c_1_bot': None,  # connector 1 disconnected from detector
                    # 'c_1_top': None,
                    # 'c_2_bot': (3, 1),  # connector 2 disconnected from detector 7-16-26
                    # 'c_2_top': (3, 2),
                    'c_3_bot': (3, 3),  # Runs along x direction, indicates y hit location
                    'c_3_top': (3, 4),
                    'c_4_bot': (3, 5),
                    'c_4_top': (3, 6),
                    'c_5_bot': (3, 7),  # Runs along y direction, indicates x hit location
                    'c_5_top': (3, 8),
                    'c_6_bot': (4, 1),
                    'c_6_top': (4, 2),
                    'c_7_bot': (4, 3),
                    'c_7_top': (4, 4),
                    'c_8_bot': (4, 5),
                    'c_8_top': (4, 6),
                    'c_9_bot': (4, 7),
                    'c_9_top': (4, 8),
                    # 'c_10_bot': None,  # connector 10 disconnected from detector
                    # 'c_10_top': None,
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    # 'c_2_bot': 'rotated_inverted',  # connector 2 disconnected 7-16-26
                    # 'c_2_top': 'rotated_inverted',
                    'c_3_bot': 'rotated_inverted',
                    'c_3_top': 'rotated_inverted',
                    'c_4_bot': 'rotated_inverted',
                    'c_4_top': 'rotated_inverted',
                    'c_5_bot': 'rotated_inverted',
                    'c_5_top': 'rotated_inverted',
                    'c_6_bot': 'rotated_inverted',
                    'c_6_top': 'rotated_inverted',
                    'c_7_bot': 'rotated_inverted',
                    'c_7_top': 'rotated_inverted',
                    'c_8_bot': 'rotated_inverted',
                    'c_8_top': 'rotated_inverted',
                    'c_9_bot': 'rotated_inverted',
                    'c_9_top': 'rotated_inverted',
                },
            },
            {
                'name': 'mx17_2',
                'description': 'Bulked by Arnaud June 12. Giant pillars on parts of the detector.',
                'det_type': 'mx17',
                'resist_type': 'strip',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p2_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 90,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 6),
                    'resist': (3, 4),
                },
                'dream_feus': {
                    'x_1': (6, 1),  # Runs along x direction, indicates y hit location
                    'x_2': (6, 2),
                    'x_3': (6, 3),
                    'x_4': (6, 4),
                    'x_5': (6, 5),
                    'x_6': (6, 6),
                    'x_7': (6, 7),
                    'x_8': (6, 8),
                    'y_1': (8, 1),  # Runs along y direction, indicates x hit location
                    'y_2': (8, 2),
                    'y_3': (8, 3),
                    'y_4': (8, 4),
                    'y_5': (8, 5),
                    'y_6': (8, 6),
                    'y_7': (8, 7),
                    'y_8': (8, 8),
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'x_1': 'inverted',
                    'x_2': 'inverted',
                    'x_3': 'inverted',
                    'x_4': 'inverted',
                    'x_5': 'inverted',
                    'x_6': 'inverted',
                    'x_7': 'inverted',
                    'x_8': 'inverted',
                    'y_1': 'inverted',
                    'y_2': 'inverted',
                    'y_3': 'inverted',
                    'y_4': 'inverted',
                    'y_5': 'inverted',
                    'y_6': 'inverted',
                    'y_7': 'inverted',
                    'y_8': 'inverted',
                },
            },
            {
                'name': 'mx17_3',
                'description': 'Bulked by Stephan June 15',
                'det_type': 'mx17',
                'resist_type': 'strip',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p2_z'] + self.bench_geometry['board_thickness'],  # mm  on P2 (upper)
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 90,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 7),
                    'resist': (3, 4),
                },
                'dream_feus': {
                    'x_1': (7, 1),  # Runs along x direction, indicates y hit location
                    'x_2': (7, 2),
                    'x_3': (7, 3),
                    'x_4': (7, 4),
                    'x_5': (7, 5),
                    'x_6': (7, 6),
                    'x_7': (7, 7),
                    'x_8': (7, 8),
                    'y_1': (8, 1),  # Runs along y direction, indicates x hit location
                    'y_2': (8, 2),
                    'y_3': (8, 3),
                    'y_4': (8, 4),
                    'y_5': (8, 5),
                    'y_6': (8, 6),
                    'y_7': (8, 7),
                    'y_8': (8, 8),
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'x_1': 'inverted',
                    'x_2': 'inverted',
                    'x_3': 'inverted',
                    'x_4': 'inverted',
                    'x_5': 'inverted',
                    'x_6': 'inverted',
                    'x_7': 'inverted',
                    'x_8': 'inverted',
                    'y_1': 'inverted',
                    'y_2': 'inverted',
                    'y_3': 'inverted',
                    'y_4': 'inverted',
                    'y_5': 'inverted',
                    'y_6': 'inverted',
                    'y_7': 'inverted',
                    'y_8': 'inverted',
                },
            },
            {
                'name': 'mx17_4',
                'description': 'Bulked by Stephan in batch of 3 on June 22. Was board C. Had a few bubbles, but '
                               'appears that the pillars underneath were still there, so just no caps',
                'det_type': 'mx17',
                'resist_type': 'strip',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p2_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 90,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 6),
                    'resist': (3, 4),
                },
                'dream_feus': {
                    'x_1': (6, 1),  # Runs along x direction, indicates y hit location
                    'x_2': (6, 2),
                    'x_3': (6, 3),
                    'x_4': (6, 4),
                    'x_5': (6, 5),
                    'x_6': (6, 6),
                    'x_7': (6, 7),
                    'x_8': (6, 8),
                    'y_1': (8, 1),  # Runs along y direction, indicates x hit location
                    'y_2': (8, 2),
                    'y_3': (8, 3),
                    'y_4': (8, 4),
                    'y_5': (8, 5),
                    'y_6': (8, 6),
                    'y_7': (8, 7),
                    'y_8': (8, 8),
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'x_1': 'inverted',
                    'x_2': 'inverted',
                    'x_3': 'inverted',
                    'x_4': 'inverted',
                    'x_5': 'inverted',
                    'x_6': 'inverted',
                    'x_7': 'inverted',
                    'x_8': 'inverted',
                    'y_1': 'inverted',
                    'y_2': 'inverted',
                    'y_3': 'inverted',
                    'y_4': 'inverted',
                    'y_5': 'inverted',
                    'y_6': 'inverted',
                    'y_7': 'inverted',
                    'y_8': 'inverted',
                },
            },
            {
                'name': 'mx17_6',
                'description': 'Bulked by Stephan June 24 (?). Was board D. Stephan redid the lamination after first '
                               'layer had wrinkles a few times until good. In the end, a column of waves in the mesh '
                               'and maybe a spot with no pillar caps.',
                'det_type': 'mx17',
                'resist_type': 'strip',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p1_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 90,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 6),
                    'resist': (3, 3),
                },
                'dream_feus': {
                    'x_1': (3, 1),  # Runs along x direction, indicates y hit location
                    'x_2': (3, 2),
                    'x_3': (3, 3),
                    'x_4': (3, 4),
                    'x_5': (3, 5),
                    'x_6': (3, 6),
                    'x_7': (3, 7),
                    'x_8': (3, 8),
                    'y_1': (4, 1),  # Runs along y direction, indicates x hit location
                    'y_2': (4, 2),
                    'y_3': (4, 3),
                    'y_4': (4, 4),
                    'y_5': (4, 5),
                    'y_6': (4, 6),
                    'y_7': (4, 7),
                    'y_8': (4, 8),
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'x_1': 'inverted',
                    'x_2': 'inverted',
                    'x_3': 'inverted',
                    'x_4': 'inverted',
                    'x_5': 'inverted',
                    'x_6': 'inverted',
                    'x_7': 'inverted',
                    'x_8': 'inverted',
                    'y_1': 'inverted',
                    'y_2': 'inverted',
                    'y_3': 'inverted',
                    'y_4': 'inverted',
                    'y_5': 'inverted',
                    'y_6': 'inverted',
                    'y_7': 'inverted',
                    'y_8': 'inverted',
                },
            },
            {
                'name': 'mx17_7',
                'description': 'Bulked by Stephan in batch of 3 on June 22. Was board B. Had one or two bubbles, but '
                               'appears that the pillars underneath were still there, so just no caps',
                'det_type': 'mx17',
                'resist_type': 'strip',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p2_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 90,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 7),
                    'resist': (3, 4),
                },
                'dream_feus': {
                    'x_1': (6, 1),  # Runs along x direction, indicates y hit location
                    'x_2': (6, 2),
                    'x_3': (6, 3),
                    'x_4': (6, 4),
                    'x_5': (6, 5),
                    'x_6': (6, 6),
                    'x_7': (6, 7),
                    'x_8': (6, 8),
                    'y_1': (8, 1),  # Runs along y direction, indicates x hit location
                    'y_2': (8, 2),
                    'y_3': (8, 3),
                    'y_4': (8, 4),
                    'y_5': (8, 5),
                    'y_6': (8, 6),
                    'y_7': (8, 7),
                    'y_8': (8, 8),
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'x_1': 'inverted',
                    'x_2': 'inverted',
                    'x_3': 'inverted',
                    'x_4': 'inverted',
                    'x_5': 'inverted',
                    'x_6': 'inverted',
                    'x_7': 'inverted',
                    'x_8': 'inverted',
                    'y_1': 'inverted',
                    'y_2': 'inverted',
                    'y_3': 'inverted',
                    'y_4': 'inverted',
                    'y_5': 'inverted',
                    'y_6': 'inverted',
                    'y_7': 'inverted',
                    'y_8': 'inverted',
                },
            },
            {
                'name': 'clas12_test_1',
                'description': 'tested for daq',
                'det_type': 'clas12_test',
                'resist_type': 'strip',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p1_z'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 7),
                    'resist': (3, 0),
                },
                'dream_feus': {
                    'x_1': (3, 1),  # Runs along x direction, indicates y hit location
                    'x_2': (3, 2),
                    'x_3': (3, 3),
                    'x_4': (3, 4),
                    'x_5': (3, 5),
                    'x_6': (3, 6),
                    'x_7': (3, 7),
                    'x_8': (3, 8),
                    'y_1': (4, 1),  # Runs along y direction, indicates x hit location
                    'y_2': (4, 2),
                    'y_3': (4, 3),
                    'y_4': (4, 4),
                    'y_5': (4, 5),
                    'y_6': (4, 6),
                    'y_7': (4, 7),
                    'y_8': (4, 8),
                },
                'dream_feu_orientation': {  # If connector is normal, inverted, rotated, or rotated_inverted
                    'x_1': 'inverted',
                    'x_2': 'inverted',
                    'x_3': 'inverted',
                    'x_4': 'inverted',
                    'x_5': 'inverted',
                    'x_6': 'inverted',
                    'x_7': 'inverted',
                    'x_8': 'inverted',
                    'y_1': 'inverted',
                    'y_2': 'inverted',
                    'y_3': 'inverted',
                    'y_4': 'inverted',
                    'y_5': 'inverted',
                    'y_6': 'inverted',
                    'y_7': 'inverted',
                    'y_8': 'inverted',
                },
            },
            {
                'name': 'banco_ladder157',
                'det_type': 'banco',
                'det_center_coords': {  # Center of detector
                    'x': -13.54 - 40,  # mm  Guess from previous alignment plus shift measurement
                    'y': -34.27 + 30,  # mm
                    'z': 842.20,  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 180,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': 'banco',
                'dream_feus': 'banco',
            },
            {
                'name': 'banco_ladder162',
                'det_type': 'banco',
                'det_center_coords': {  # Center of detector
                    'x': -15.41 - 40,  # mm  Guess from previous alignment plus shift measurement
                    'y': -34.27 + 30,  # mm
                    'z': 853.26,  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': 'banco',
                'dream_feus': 'banco',
            },
            {
                'name': 'banco_ladder160',
                'det_type': 'banco',
                'det_center_coords': {  # Center of detector
                    'x': -13.21 - 40,  # mm  Guess from previous alignment plus shift measurement
                    'y': -34.39 + 30,  # mm
                    'z': 971.45,  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 180,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': 'banco',
                'dream_feus': 'banco',
            },
            {
                'name': 'banco_ladder163',
                'det_type': 'banco',
                'det_center_coords': {  # Center of detector
                    'x': -15.03 - 40,  # mm  Guess from previous alignment plus shift measurement
                    'y': -34.46 + 30,  # mm
                    'z': 982.50,  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': 'banco',
                'dream_feus': 'banco',
            },
            {
                'name': 'urw_strip',
                'det_type': 'urw_strip',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': self.bench_geometry['p1_z'] + self.bench_geometry['bottom_level_z'] +
                         5 * self.bench_geometry['level_z_spacing'] + self.bench_geometry['board_thickness'],  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 0),
                    'resist_1': (3, 1)
                },
                'dream_feus': {
                    'x_1': (6, 5),  # Runs along x direction, indicates y hit location
                    'x_2': (6, 6),
                    'y_1': (6, 7),  # Runs along y direction, indicates x hit location
                    'y_2': (6, 8),
                },
            },
            {
                'name': 'urw_inter',
                'det_type': 'urw_inter',
                'det_center_coords': {  # Center of detector
                    # 'x': 0,  # mm
                    # 'y': 0,  # mm
                    # 'z': self.bench_geometry['p1_z'] + self.bench_geometry['bottom_level_z'] +
                    #      4 * self.bench_geometry['level_z_spacing'] + self.bench_geometry['board_thickness'],  # mm
                    'x': 10,  # mm
                    'y': 40,  # mm
                    'z': 712.7,  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 1),
                    'resist_1': (3, 2)
                },
                'dream_feus': {
                    'x_1': (6, 1),  # Runs along x direction, indicates y hit location
                    'x_2': (6, 2),
                    'y_1': (6, 3),  # Runs along y direction, indicates x hit location
                    'y_2': (6, 4),
                },
            },
            {
                'name': 'p2_3',
                'det_type': 'p2',
                'det_center_coords': {  # Center of detector
                    # 'x': 0,  # mm
                    # 'y': 0,  # mm
                    # 'z': self.bench_geometry['p1_z'] + self.bench_geometry['bottom_level_z'] +
                    #      4 * self.bench_geometry['level_z_spacing'] + self.bench_geometry['board_thickness'],  # mm
                    'x': 10,  # mm
                    'y': 40,  # mm
                    'z': 712.7,  # mm
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {
                    'drift': (0, 6),
                    'mesh_1': (0, 7)
                },
                'dream_feus': {
                    'x_1': (6, 1),
                    'x_2': (6, 2),
                },
            },
            {
                'name': 'm3_bot_bot',
                'det_type': 'm3',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': 24,  # mm  28 from geometry diagram, 24 from m3 config json
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {  # Don't know HTM# matching to geometric layout, guessing
                    'drift': (0, 8),
                    'mesh_1': (3, 8)
                },
                'dream_feus': {  # Guesses
                    'x_1': (1, 1),  # Runs along x direction, indicates y hit location
                    'y_1': (1, 2),  # Runs along y direction, indicates x hit location
                },
            },
            {
                'name': 'm3_bot_top',
                'det_type': 'm3',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': 144,  # mm  145 from geometry diagram, 144 from m3 config json
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {  # Don't know HTM# matching to geometric layout, guessing
                    'drift': (0, 9),
                    'mesh_1': (3, 9)
                },
                'dream_feus': {  # Guesses
                    'x_1': (1, 3),  # Runs along x direction, indicates y hit location
                    'y_1': (1, 4),  # Runs along y direction, indicates x hit location
                },
            },
            {
                'name': 'm3_top_bot',
                'det_type': 'm3',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': 1185,  # mm  1163 + 28 from geometry diagram, 1185 from m3 config json
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {  # Don't know HTM# matching to geometric layout, guessing
                    'drift': (0, 10),
                    'mesh_1': (3, 10)
                },
                'dream_feus': {  # Guesses
                    'x_1': (1, 5),  # Runs along x direction, indicates y hit location
                    'y_1': (1, 6),  # Runs along y direction, indicates x hit location
                },
            },
            {
                'name': 'm3_top_top',
                'det_type': 'm3',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': 1302,  # mm  1163 + 145 from geometry diagram, 1302 from m3 config json
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'hv_channels': {  # Don't know HTM# matching to geometric layout, guessing
                    'drift': (0, 11),
                    'mesh_1': (3, 11)
                },
                'dream_feus': {  # Guesses
                    'x_1': (1, 7),  # Runs along x direction, indicates y hit location
                    'y_1': (1, 8),  # Runs along y direction, indicates x hit location
                },
            },
            {
                'name': 'scintillator_top',
                'det_type': 'scintillator',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': 1412,  # mm  1163 + 145 + 110 from geometry diagram
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'dream_feus': {
                    'xy': (3, 4),
                },
                'dream_feu_channels': {
                    'xy': (3, 4, 21),
                }
            },
            {
                'name': 'scintillator_bottom',
                'det_type': 'scintillator',
                'det_center_coords': {  # Center of detector
                    'x': 0,  # mm
                    'y': 0,  # mm
                    'z': 24 - 100,  # mm  24 - 100 from geometry diagram
                },
                'det_orientation': {
                    'x': 0,  # deg  Rotation about x axis
                    'y': 0,  # deg  Rotation about y axis
                    'z': 0,  # deg  Rotation about z axis
                },
                'dream_feus': {
                    'xy': (3, 4),
                },
                'dream_feu_channels': {
                    'xy': (3, 4, 20),
                }
            },
        ]

        if not self.write_all_dectors_to_json:
            self.detectors = [det for det in self.detectors if det['name'] in self.included_detectors]

        # Derive the active FEUs (and their used connectors) from the included detectors so
        # dream_daq_control can enable only those FEUs in the .cfg and set per-Dream roles.
        # Skip when writing the full detector list to a json template.
        if not self.write_all_dectors_to_json and self.dream_daq_info.get('set_feus_from_detectors', False):
            feu_connectors = self.get_active_feu_connectors()
            self.dream_daq_info['included_feus'] = sorted(feu_connectors)
            self.dream_daq_info['feu_connectors'] = feu_connectors
            self.dream_daq_info['trigger_feu'] = self.m3_feu_num

    def get_active_feu_connectors(self):
        """Map each FEU used by the included detectors to the sorted list of its used connectors.

        Each dream_feus value is a (feu_number, connector) tuple. Connectors are 1-based (1..8) and
        correspond to FEU Dream indices 0..7 (Dream index = connector - 1). String-valued maps
        (e.g. 'banco') carry no explicit FEU/connector numbers and are skipped.
        """
        feu_connectors = {}
        for det in self.detectors:
            dream_feus = det.get('dream_feus')
            if not isinstance(dream_feus, dict):
                continue
            for mapping in dream_feus.values():
                if isinstance(mapping, (tuple, list)) and len(mapping) >= 2:
                    feu, connector = int(mapping[0]), int(mapping[1])
                    feu_connectors.setdefault(feu, set()).add(connector)
        return {feu: sorted(conns) for feu, conns in feu_connectors.items()}

    def get_active_feus(self):
        """Sorted FEU numbers used by the included detectors (keys of get_active_feu_connectors)."""
        return sorted(self.get_active_feu_connectors())

    def write_to_file(self, file_path):
        with open(file_path, 'w') as file:
            json.dump(self.__dict__, file, indent=4)

    def load_from_file(self, file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
            self.__dict__.clear()
            self.__dict__.update(data)


if __name__ == '__main__':
    out_run_dir = '/local/home/usernsw/Cosmic_Bench_DAQ_Control/config/json_run_configs'
    config_name = 'run_config.json'
    config = Config()
    config.write_to_file(f'{out_run_dir}/{config_name}')
    print('donzo')
