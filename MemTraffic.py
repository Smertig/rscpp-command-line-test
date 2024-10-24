from argparse import ArgumentParser
from os import path, makedirs
import json
from subprocess import PIPE
import shutil
import subprocess
import time

import common

args = common.argparser.parse_args()
env = common.load_env(args)

profiler_dir     = env.profiler_dir
console_profiler = path.join(profiler_dir, "ConsoleProfiler.exe")
snapshot_dumper  = path.join(profiler_dir, "JetBrains.Timeline.Tools.Snapshot.Dumper.exe")

snapshots_home = path.join(env.cli_test_dir, "snapshots-home")
makedirs(snapshots_home, exist_ok=True)


def process_project(project_name, project):
    start_time = time.time()

    project = common.read_conf_if_needed(project)
    project_dir, sln_file = common.prepare_project(project_name, project, None)

    project_to_check = project.get("project to check")
    msbuild_props = project.get("msbuild properties")
    inspect_code_args, report_file, _ = common.inspect_code_run_arguments(project_dir, sln_file, project_to_check, msbuild_props)
    inspect_code_args.append("-j=1") # reduce nondetermenism
    #inspect_code_args.append("--debug")
    snapshot_dir = path.join(snapshots_home, project_name)
    makedirs(snapshot_dir, exist_ok=True)
    snapshot_path = path.join(snapshot_dir, "snapshot.dtt")
    profiler_args = [console_profiler, "start", "--profiling-type=Timeline",
                     "--disable-tpl", "--overwrite", "--save-to=" + snapshot_path,
                     env.inspect_code_path_x86, "--"] + inspect_code_args
    #print(subprocess.list2cmdline(profiler_args))
    process = subprocess.Popen(profiler_args, stdout=PIPE, text=True, encoding='cp1251')
    out, err = process.communicate()
    exit_code = process.wait()
    if exit_code != 0:
        print("Error: exit code = " + str(exit_code))
    if err:
        print("Error:")
        print(err)

    local_config = project['stable']
    expected_files_count = local_config["inspected files count"]
    actual_files_count = common.inspected_files_count(out)
    if expected_files_count != actual_files_count:
        print(out)
        print(f"expected count of inspected files is {expected_files_count}, but actual is {actual_files_count}")
        return None

    subprocess.run([snapshot_dumper, "-i", snapshot_path, "-A"], check=True, stdout=PIPE)
    with open(path.join(snapshot_dir, "snapshot.dtt.alloc.stats.txt")) as f:
        actual_traffic = int(f.read()) // (1 << 20)

    expected_traffic = local_config.get("mem traffic")
    if expected_traffic:
        relative_delta = (actual_traffic - expected_traffic) / expected_traffic * 100
        if abs(relative_delta) < (3.0 if expected_traffic < 1000 else 0.5):
            shutil.rmtree(snapshot_dir)
        print("expected traffic is {0} MB, actual traffic is {1} MB; delta = {2:.2f}%"
              .format(expected_traffic, actual_traffic, relative_delta), flush=True)
    else:
        print("traffic is {0} MB".format(actual_traffic), flush=True)

    elapsed_time = common.duration(start_time, time.time())
    print("elapsed time: {0}".format(elapsed_time), flush=True)


start_time = time.time()

for project_name, _ in common.parse_projects(args.project):
    print("processing project {0}...".format(project_name), flush=True)
    process_project(project_name, common.projects[project_name])
    print('-------------------------------------------------------', flush=True)

print("Total time: " + common.duration(start_time, time.time()))
