import datetime
import json
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import git
import os
from subprocess import Popen, PIPE
from typing import Optional, Tuple, List

import common
import util.error_parser


def print_errors(title, errors):
    assert errors, errors
    json_errors = ("  " + json.dumps({"file": f, "line": l, "message": m}) for f, l, m in sorted(errors))
    print(f"{title} errors:")
    print(",\n".join(json_errors))


def print_file_wide_errors(title, errors):
    assert errors, errors
    json_errors = ("  " + json.dumps(error) for error in errors)
    print(f"{title} file-wide errors:")
    print(",\n".join(json_errors))


def is_flaky(error: dict) -> bool:
    return error.get("flaky", False)


def check_report(report_file, known_errors, known_file_errors) -> Tuple[str, dict]:
    def get_error_id(error):
        return error["file"], int(error["line"]), error["message"]

    results: List[str] = []
    error_mismatch = False

    xml_doc = ET.parse(report_file)
    issue_severities = {issue_type.get("Id"): issue_type.get("Severity")
                        for issue_type in xml_doc.getroot().findall("IssueTypes")[0]}

    def get_severity(issue) -> str:
        return issue.get("Severity") or issue_severities[issue.get("TypeId")]

    issue_nodes = xml_doc.getroot().findall("Issues")[0]
    if len(issue_nodes) == 0:
        print("No compilation errors found")

        known_stable_errors = [get_error_id(error) for error in known_errors if not is_flaky(error)]
        if known_stable_errors:
            print_errors("Expected", known_stable_errors)
            results.append(f"no compilation errors found, but {len(known_stable_errors)} errors were expected")
            error_mismatch = True

        known_stable_file_errors = [error for error in known_file_errors if not is_flaky(error)]
        if known_stable_file_errors:
            print_file_wide_errors("Expected", known_stable_file_errors)
            results.append(f"no compilation errors found, but {len(known_stable_errors)} file errors were expected")
            error_mismatch = True
    else:
        actual_errors = set((issue.get("File"), int(issue.get("Line", "0")), issue.get("Message"))
                            for issue in issue_nodes.iter("Issue")
                            if get_severity(issue) == 'ERROR')
        if known_file_errors:
            known_error_files = set(error["file"] for error in known_file_errors)
            actual_error_files = set(error[0] for error in actual_errors)

            # Make sure that at least one error belongs to every known file with errors
            missing_file_errors = list(known_file_error for known_file_error in known_file_errors if known_file_error["file"] not in actual_error_files)
            if missing_file_errors:
                print_file_wide_errors("Missing", missing_file_errors)
                error_mismatch = True

            # Filter out known file-wide errors
            excluded_actual_errors = set(error for error in actual_errors if error[0] in known_error_files)
            actual_errors = set(error for error in actual_errors if error[0] not in known_error_files)

            if error_mismatch:
                results.append(f"{len(missing_file_errors)} files without expected errors")
            else:
                print(f"{len(excluded_actual_errors)} errors in {len(known_error_files)} files found as expected")

        if known_errors:
            unexpected_errors = actual_errors - set(get_error_id(error) for error in known_errors)
            if unexpected_errors:
                print_errors("Unexpected", unexpected_errors)
                error_mismatch = True

            missing_errors = set(get_error_id(error) for error in known_errors if not is_flaky(error)) - actual_errors
            if missing_errors:
                print_errors("Missing", missing_errors)
                error_mismatch = True

            if error_mismatch:
                results.append("expected and actual set of errors differ")
            else:
                print(f"{len(actual_errors)} standalone errors found as expected")
        elif actual_errors:
            print_errors("Unexpected", actual_errors)
            results.append(f"unexpected {len(actual_errors)} errors found")
            error_mismatch = True

    return "\n".join(results), {
        'tool_version': xml_doc.getroot().attrib['ToolsVersion'],
        'error_mismatch': error_mismatch
    }


def run_inspect_code(project_dir, sln_file, project_to_check, msbuild_props, use_x64: bool, snapshot_path: str = None):
    args, report_file, err_file = common.inspect_code_run_arguments(project_dir, sln_file, project_to_check, msbuild_props)
    args.insert(0, env.inspect_code_path_x64 if use_x64 else env.inspect_code_path_x86)

    if snapshot_path:
        # TODO: support for x86 somehow?
        assert use_x64, "dotnet-trace doesn't work with x86 inspect code tool"

        dotnet_args = ["dotnet", "exec", "--runtimeconfig", env.inspect_code_runtime_config_path]
        args = dotnet_args + args

    print('[run_inspect_code]', subprocess.list2cmdline(args), flush=True)
    process = Popen(args, stdout=PIPE, stderr=PIPE, text=True, encoding='cp1251')
    start = time.time()

    if snapshot_path:
        time.sleep(1)
        inspect_code_pid = process.pid
        profiler_args = ["dotnet-trace",
                         "collect",
                         "--profile", "gc-verbose",
                         "--output", snapshot_path,
                         "--process-id", str(inspect_code_pid),
                         ]

        profiler_process = Popen(profiler_args)
        print(f"[run_inspect_code] Running profiler for pid={inspect_code_pid}..", flush=True)

    while True:
        try:
            out, err = process.communicate(timeout=60)
            break
        except subprocess.TimeoutExpired:
            print(f"[run_inspect_code] Still running.. elapsed time: {common.duration(start, time.time())}", flush=True)
            pass

    exit_code = process.wait()
    end = time.time()
    if exit_code != 0:
        print(f"[run_inspect_code] Error: exit code = {exit_code}", flush=True)

    if err:
        max_displayed_len = 1_000_000
        print('::group::stderr')
        if len(err) > max_displayed_len:
            print(f"[run_inspect_code] stderr:\n{err[:max_displayed_len]}...\n...\n...(too big: {len(err)} bytes)")
        else:
            print(f"[run_inspect_code] stderr:\n{err}")
        print('::endgroup::', flush=True)

    print('::group::stdout')
    print(f"[run_inspect_code] stdout:\n{out}")
    print('::endgroup::', flush=True)

    if snapshot_path:
        profiler_process.wait()

    if os.path.exists(err_file):
        print(f"[run_inspect_code] Non-empty errors log", flush=True)
    else:
        print(f"[run_inspect_code] No runtime errors", flush=True)

    print("[run_inspect_code] Elapsed time: " + common.duration(start, end), flush=True)
    return report_file, err_file, out


def check_project(project, project_dir, sln_file, branch: Optional[str]) -> Tuple[str, dict]:
    project_to_check = project.get("project to check")
    msbuild_props = project.get("msbuild properties")
    use_x86 = env.is_x86 and project.get("only x64", False) is False
    use_x64 = not use_x86
    trace_memory = use_x64
    local_config = project["latest"][branch] if branch else project["stable"]

    if trace_memory:
        os.makedirs(env.snapshots_home, exist_ok=True)
        snapshot_path = os.path.join(env.snapshots_home, 'snapshot.dtt')
    else:
        snapshot_path = None

    start_date = datetime.datetime.utcnow()
    start_time = time.time()
    report_file, err_file, output = run_inspect_code(project_dir, sln_file, project_to_check, msbuild_props, use_x64, snapshot_path)
    end_time = time.time()

    if trace_memory:
        with common.cwd(env.trace_inspector_dir):
            inspector_args = ["dotnet", "run", snapshot_path]
            print("[check_project] Running trace inspector:", subprocess.list2cmdline(inspector_args), flush=True)
            memory_stats_json = subprocess.check_output(inspector_args)
            memory_stats = json.loads(memory_stats_json)

            actual_traffic = memory_stats["AllocationAmount"] / (1 << 20)
    else:
        actual_traffic = None

    expected_files_count = local_config.get("inspected files count")
    actual_files_count = common.inspected_files_count(output)
    if expected_files_count:
        if expected_files_count != actual_files_count:
            print(f"[check_project] expected count of inspected files is {expected_files_count}, but actual is {actual_files_count}", flush=True)
    else:
        print(f"[check_project] count of inspected files is {actual_files_count}", flush=True)

    if actual_traffic is not None:
        expected_traffic = local_config.get("mem traffic")
        if expected_traffic:
            relative_delta = (actual_traffic - expected_traffic) / expected_traffic * 100
            if abs(relative_delta) < (3.0 if expected_traffic < 1000 else 0.5):
                shutil.rmtree(env.snapshots_home)

            print(f"[check_project] expected traffic is {expected_traffic:0.1f} MB, "
                  f"actual traffic is {actual_traffic:0.1f} MB; "
                  f"delta = {relative_delta:.2f}%", flush=True)
        else:
            print(f"[check_project] traffic is {actual_traffic:0.1f} MB", flush=True)

    result, report = check_report(report_file, local_config.get("known errors", []), local_config.get("known file errors", []))
    report |= {
        'project': project_to_check,
        'timestamp': start_date.timestamp(),
        'elapsed_time': end_time - start_time,
        'x64': use_x64,
        'actual_files_count': actual_files_count,
        'expected_files_count': expected_files_count,
    }

    if actual_traffic:
        report['memory_traffic'] = actual_traffic

    if os.path.exists(err_file):
        with open(err_file, encoding='cp1251') as f:
            runtime_errors = util.error_parser.parse_logs(f.read())

        print(f"[check_project] found {len(runtime_errors)} runtime error(s):", flush=True)
        if runtime_errors:
            for error in runtime_errors:
                analyzer_short_name = error.analyzer.split(".")[-1]
                print(f"[check_project]   \"{error.file_path}\" {analyzer_short_name} => {error.message}", flush=True)

            result = f'({len(runtime_errors)} errors in logs) {result}'.rstrip()

    return result, report


def process_project_with_cmake_generator(project, project_name, cmake_generator: str, branch: Optional[str]) -> Tuple[str, dict]:
    project_dir, sln_file = common.prepare_project(project_name, project, cmake_generator, branch)
    if env.is_dry_run:
        return f'({project_name}-{cmake_generator}) dry run: {sln_file}', dict()

    result, report = check_project(project, project_dir, sln_file, branch)
    if result:
        result = f"({cmake_generator}) {result}"
    return result, report


def process_project(project_name, project, branch: Optional[str]) -> Tuple[str, dict]:
    project = common.read_conf_if_needed(project)

    available_toolchains = common.get_compatible_toolchains(project)
    if not available_toolchains:
        return f'({project_name}) no available toolchains found', {}

    if "custom build tool" in project:
        project_dir, sln_file = common.prepare_project(project_name, project, None, branch)
        if env.is_dry_run:
            return f'({project_name}) dry run: {sln_file}', dict()

        result, default_report = check_project(project, project_dir, sln_file, branch)
        toolchain_reports = {
            'default': default_report
        }
    else:
        result = ''
        toolchain_reports = {}
        for generator in available_toolchains:
            local_result, local_report = process_project_with_cmake_generator(project, project_name, generator, branch)
            toolchain_reports[generator] = local_report
            if local_result:
                result = local_result
                break

    report = {'toolchains': toolchain_reports}

    try:
        with git.Repo(env.get_project_dir(project_name)) as repo:
            last_commit = repo.commit()
            report['repo'] = {
                'url': repo.remote().url,
                'ref': last_commit.hexsha,
                'message': last_commit.message,
                'timestamp': last_commit.committed_datetime.timestamp()
            }
    except:
        pass

    return result, report


common.argparser.add_argument("--report-path", dest="report_path")
args = common.argparser.parse_args()
env = common.load_env(args)


def main():
    summary = []
    start_time = time.time()

    full_report = {}
    for project_name, project_branch in common.parse_projects(args.project):
        print(f"processing project {project_name} (branch: {project_branch})...", flush=True)

        try:
            result, report = process_project(project_name, common.projects[project_name], project_branch)
        except Exception as e:
            error_info = traceback.format_exc()
            print(error_info, flush=True)

            result = f"exception: {e}"
            report = {
                'error': {
                    'exception': str(e),
                    'error_info': error_info
                }
            }

        report_key = f"{project_name}:{project_branch}" if project_branch else project_name
        full_report[report_key] = report

        if result:
            summary.append(project_name + ": " + result)

        print('-------------------------------------------------------', flush=True)

    # Dump report if needed
    report_path = args.report_path
    if report_path:
        common.create_parents(report_path)
        with open(report_path, 'w') as f_report:
            json.dump(full_report, f_report, indent=4)

    print("Total time: " + common.duration(start_time, time.time()), flush=True)
    if len(summary) == 0:
        print("Summary: OK")
        return 0
    else:
        print("Summary: Fail")
        for s in summary:
            print("    " + s)
        return 1


if __name__ == '__main__':
    ret = main()
    sys.exit(ret)
