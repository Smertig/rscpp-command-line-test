import os
import sys
from os import path, makedirs
from subprocess import PIPE
import subprocess
import xml.etree.ElementTree as ET
import json
import requests
import io
from argparse import ArgumentParser
from zipfile import ZipFile
from typing import Optional, List
from contextlib import contextmanager


sys.stdout.reconfigure(encoding='utf-8')

# assert 'VsInstallRoot' in os.environ, 'Missing VsInstallRoot environment variable'
# assert 'VCTargetsPath' in os.environ, 'Missing VCTargetsPath environment variable'


VS_CMAKE_GENERATORS = {
    "2017-x64": {
        "cmake options": [
            "-G", "Visual Studio 15 2017 Win64"
        ],
        "vcpkg_triplet": "x64-windows"
    },
    "2019-x64": {
        "cmake options": [
            "-G", "Visual Studio 16 2019",
            "-A", "x64"
        ],
        "vcpkg_triplet": "x64-windows"
    },
    "2022-x64": {
        "cmake options": [
            "-G", "Visual Studio 17 2022",
            "-A", "x64"
        ],
        "vcpkg_triplet": "x64-windows"
    },
    "clang-cl-2019-x86": {
        "cmake options": [
            "-G", "Visual Studio 16 2019",
            "-A", "Win32",
            "-T", "ClangCL"
        ],
        "vcpkg_triplet": "x86-windows-clang"
    },
    "clang-cl-2019-x64": {
        "cmake options": [
            "-G", "Visual Studio 16 2019",
            "-A", "x64",
            "-T", "ClangCL"
        ],
        "vcpkg_triplet": "x64-windows-clang"
    },
}


class Environment:
    def __init__(self, args):
        self._args = args
        if args.env_path:
            with open(args.env_path) as f:
                self._env = json.load(f)
        else:
            self._env = None

        self._build_directory = args.build_directory or self._get_env("build directory") or self._detect_build_dir()
        self._projects_cache_directory = args.projects_cache_directory or self._get_env("projects cache dir")
        self._supported_generators = args.supported_generators or self._get_env("supported generators") or []
        self._vcpkg_directory = args.vcpkg_directory or self._get_env("vcpkg dir")
        self._verbose = args.verbose
        self._cli_test_dir = os.path.dirname(os.path.abspath(__file__))
        self._is_ci = args.is_ci
        self._is_x86 = args.is_x86

        assert self._build_directory, 'Missing build directory'

    def _get_env(self, key: str) -> Optional[str]:
        if self._env is None:
            return None
        return self._env.get(key)

    @staticmethod
    def _detect_build_dir() -> str:
        dotnet_tools_path = os.environ['USERPROFILE'] + '/.dotnet/tools/.store'
        tools_list = os.listdir(f'{dotnet_tools_path}/jetbrains.resharper.globaltools')
        if not tools_list:
            raise RuntimeError('No installed JetBrains.ReSharper.GlobalTools')

        last_version = sorted(tools_list)[-1]
        return f"{dotnet_tools_path}/jetbrains.resharper.globaltools/{last_version}/jetbrains.resharper.globaltools/{last_version}/tools/netcoreapp3.1/any"

    @property
    def resharper_build(self) -> str:
        return self._build_directory

    @property
    def supported_generators(self) -> List[str]:
        return self._supported_generators

    @property
    def vcpkg_dir(self) -> Optional[str]:
        return self._vcpkg_directory

    @property
    def profiler_dir(self) -> str:
        profiler_dir = self._get_env("profiler directory")
        return profiler_dir or self.resharper_build

    @property
    def cli_test_dir(self) -> str:
        return self._cli_test_dir

    @property
    def trace_inspector_dir(self) -> str:
        return os.path.join(self.cli_test_dir, "trace-inspector")

    @property
    def resharper_version(self) -> Optional[str]:
        return self._get_env("resharper version")

    @property
    def computer_name(self) -> Optional[str]:
        return self._get_env("computer name")

    @property
    def caches_home(self) -> str:
        return self._get_env("caches home") or path.join(self.cli_test_dir, "caches-home")

    @property
    def snapshots_home(self) -> str:
        return self._get_env("snapshots home") or path.join(self.cli_test_dir, "snapshots-home")

    def get_project_dir(self, project_name) -> str:
        projects_dir = self._projects_cache_directory or path.join(self.cli_test_dir, "projects")
        return path.join(projects_dir, project_name)

    @property
    def inspect_code_path_x86(self) -> str:
        return path.join(self.resharper_build, "inspectcode.x86.exe")

    @property
    def inspect_code_path_x64(self) -> str:
        return path.join(self.resharper_build, "inspectcode.exe")

    @property
    def inspect_code_runtime_config_path(self) -> str:
        return path.join(self.resharper_build, "inspectcode.runtimeconfig.json")

    @property
    def verbose(self) -> bool:
        return self._verbose

    @property
    def verbose_handle(self) -> Optional[int]:
        return None if self.verbose else PIPE

    @property
    def is_ci(self) -> bool:
        return self._is_ci

    @property
    def is_x86(self) -> bool:
        return self._is_x86

# TODO: remove global vars completely
_env: Environment = None


def load_env(args):
    global _env
    _env = Environment(args)
    return _env


with open("projects.json") as f:
    projects = json.load(f)


def git_clone_and_force_checkout_if_needed(target_dir, url, ref_name):
    if _env.is_ci:
        # We can do shallow clone when using CI
        if len(ref_name) != 40:
            subprocess.run(["git", "clone", "--depth", "1", "--branch", ref_name, url, target_dir], check=True, stdout=PIPE, stderr=_env.verbose_handle)
            return

        # TODO: implement shallow clone of a single commit..
        pass

    if not path.exists(path.join(target_dir, ".git")):
        subprocess.run(["git", "clone", url, target_dir], check=True)

    with cwd(target_dir):
        subprocess.run(["git", "checkout", ref_name], check=True, stdout=PIPE, stderr=_env.verbose_handle)
        subprocess.run(["git", "reset", "--hard"], check=True, stdout=PIPE, stderr=_env.verbose_handle)


def get_sources_from_git(project_input, target_dir, branch: Optional[str]):
    git_clone_and_force_checkout_if_needed(target_dir, project_input["repo"], branch or project_input["commit"])

    with cwd(target_dir):
        subrepo = project_input.get("subrepo")
        if subrepo:
            subrepo_dir = subrepo["path"]
            git_clone_and_force_checkout_if_needed(subrepo_dir, subrepo["url"], subrepo["commit"])

        custom_update_source_script = project_input.get("custom update source script")
        if custom_update_source_script:
            subprocess.run(custom_update_source_script, check=True, stdout=_env.verbose_handle)

        update_submodules_args = ["git", "submodule", "update", "--init"]
        if project_input.get("recursive", False):
            update_submodules_args.append("--recursive")
        subprocess.run(update_submodules_args, check=True, stdout=PIPE)

        root_dir = project_input.get("root")
        if root_dir:
            return path.join(target_dir, root_dir)
        else:
            return target_dir


def get_sources_from_zip(project_input, target_dir):
    root_dir = path.join(target_dir, project_input["root"])
    if not path.exists(root_dir):
        response = requests.get(project_input["url"])
        with ZipFile(io.BytesIO(response.content)) as zipfile:
            zipfile.extractall(path=target_dir)
    return root_dir


def get_sources(project_input, target_dir, branch: Optional[str]):
    kind = project_input.get("kind")
    if not kind:
        return get_sources_from_git(project_input, target_dir, branch)
    elif kind == "zip":
        assert branch is None, "specifying branch is not supported for ZIP projects"
        return get_sources_from_zip(project_input, target_dir)
    else:
        raise ValueError("Unknown source kind: {0}".format(kind))


def invoke_cmake(build_dir, cmake_generator, cmake_options, cmake_new_env, cmake_dir, required_dependencies):
    def apply_substitutions(s: str) -> str:
        return s.replace('${BUILD_DIR}', path.realpath(build_dir))

    cmd_line_args = ["cmake", cmake_dir]
    cmd_line_args += cmake_generator["cmake options"]

    if required_dependencies:
        vcpkg_dir = _env.vcpkg_dir
        if not vcpkg_dir:
            raise Exception(f"project has required dependencies {required_dependencies}, but environment doesn't contain path to vcpkg")

        with cwd(vcpkg_dir):
            print('[invoke_cmake] Running vcpkg', flush=True)
            subprocess.run(["vcpkg", "install"] + required_dependencies + ["--triplet", cmake_generator["vcpkg_triplet"]], check=True, stdout=_env.verbose_handle)

        cmd_line_args.append("-DCMAKE_TOOLCHAIN_FILE={0}/scripts/buildsystems/vcpkg.cmake".format(vcpkg_dir))

    cmake_env = os.environ.copy()
    if cmake_new_env:
        for env_key, env_value in cmake_new_env.items():
            cmake_env[env_key] = cmake_env.get(env_key, '') + apply_substitutions(env_value)

    if cmake_options:
        cmd_line_args.extend(cmake_options)
    makedirs(build_dir, exist_ok=True)

    with cwd(build_dir):
        if _env.verbose and cmake_new_env:
            print(f'[invoke_cmake] Running cmake with modified env: {cmake_env}', flush=True)

        print('[invoke_cmake] Running cmake:', subprocess.list2cmdline(cmd_line_args), flush=True)
        subprocess.run(cmd_line_args, check=True, stdout=_env.verbose_handle, env=cmake_env)

    with open(path.join(build_dir, "CMakeCache.txt")) as cmake_cache:
        for line in cmake_cache.readlines():
            if line.startswith("CMAKE_PROJECT_NAME"):
                project_name = line[line.find('=') + 1:].rstrip()
                sln_file = path.join(build_dir, project_name + ".sln")
                if not path.exists(sln_file):
                    raise Exception("solution file {0} does not exist".format(sln_file))
                return sln_file
    

proj_config_dir = path.abspath("proj-config")

def read_conf_if_needed(project):
    if isinstance(project, str):
        with open(path.join(proj_config_dir, project)) as pf:
            return json.load(pf)
    else:
        return project


def inspect_code_run_arguments(project_dir, sln_file, project_to_check, msbuild_props):
    report_file = path.join(project_dir, "resharper-report.xml")
    args = [
        "--severity=INFO",
        "-f=Xml",
        "-no-build",
        "-o=" + report_file,
        "--caches-home=" + _env.caches_home,
        "--no-swea",
        "--daemon=VISIBLE_DOCUMENT"
    ]
    if project_to_check:
        if isinstance(project_to_check, list):
            for p in project_to_check:
                args.append("--project=" + p)
        else:
            assert(isinstance(project_to_check, str))
            args.append("--project=" + project_to_check)
    if msbuild_props:
        props = ["{0}={1}".format(key, value) for key, value in msbuild_props.items()]
        args.append("--properties:" + ";".join(props))

    log_file = path.join(project_dir, "resharper-logs.log")
    err_file = path.join(project_dir, "resharper-logs.err.log")
    if os.path.exists(log_file): os.remove(log_file)
    if os.path.exists(err_file): os.remove(err_file)
    args.append("--LogLevel=INFO")
    args.append("--LogFile=" + log_file)

    args.append(sln_file)
    return args, report_file, err_file


def count_substring(text, substr):
    start = 0
    result = 0
    while True:
        start = text.find(substr, start)
        if start == -1:
            return result
        result += 1
        start += len(substr)


def inspected_files_count(inspect_code_output):
    return count_substring(inspect_code_output, "Inspecting ")


def add_entry(node, key, value):
    entry = ET.SubElement(node, "s:Boolean")
    entry.text = str(value)
    entry.set("x:Key", key)


def escape_dot_settings(s: str):
    def remap(c: str):
        assert len(c) == 1
        if c.isalnum():
            return c
        else:
            return f"_{ord(c):04X}"

    return "".join(map(remap, s))


assert escape_dot_settings("hello/world") == "hello_002Fworld"
assert escape_dot_settings("mesh_*_helpers.h") == "mesh_005F_002A_005Fhelpers_002Eh"


def generate_settings(files_to_skip):
    root = ET.Element("wpf:ResourceDictionary")
    root.set("xml:space", "preserve")
    root.set("xmlns:x", "http://schemas.microsoft.com/winfx/2006/xaml")
    root.set("xmlns:s", "clr-namespace:System;assembly=mscorlib")
    root.set("xmlns:ss", "urn:shemas-jetbrains-com:settings-storage-xaml")
    root.set("xmlns:wpf", "http://schemas.microsoft.com/winfx/2006/xaml/presentation")

    add_entry(root, "/Default/CodeInspection/CppClangTidy/EnableClangTidySupport/@EntryValue", False)

    if files_to_skip:
        for f in files_to_skip:
            section = "CodeInspection" if f.endswith('proto') else "Environment"
            add_entry(root, f"/Default/{section}/ExcludedFiles/FileMasksToSkip/={escape_dot_settings(f)}/@EntryIndexedValue", True)

    return ET.ElementTree(root)


def get_compatible_toolchains(project: dict) -> List[str]:
    project_generators = project.get("required toolchain")
    supported_generators = _env.supported_generators

    if not project_generators:
        return supported_generators

    return sorted(set(project_generators) & set(supported_generators))


def prepare_project(project_name, project, cmake_generator: Optional[str], branch: Optional[str] = None):
    target_dir = _env.get_project_dir(project_name)
    project_dir = get_sources(project["sources"], target_dir, branch)
    build_dir = path.join(project_dir, f'build-{cmake_generator}')
    abs_build_dir = path.realpath(build_dir)

    fixup_sources = project.get("fixup sources")
    if isinstance(fixup_sources, list):
        with cwd(target_dir):
            exec("\n".join(fixup_sources), {}, {})
    elif isinstance(fixup_sources, str) and fixup_sources.endswith(".py"):
        full_path = os.path.realpath(fixup_sources)
        with cwd(target_dir):
            env_copy = os.environ.copy()
            env_copy['BUILD_DIR'] = abs_build_dir
            subprocess.run(["python", full_path], check=True, stdout=_env.verbose_handle, env=env_copy)
    else:
        assert fixup_sources is None, "unknown fixup sources format, should be list[str] or path to python script"

    custom_build_tool = project.get("custom build tool")
    if custom_build_tool:
        with cwd(project_dir):
            prepare_sln_script = custom_build_tool.get("script")
            if prepare_sln_script:
                subprocess.run(prepare_sln_script, check=True, stdout=_env.verbose_handle)
            build_step = custom_build_tool.get("build step")
            if build_step:
                for step in build_step:
                    subprocess.run(step.split(), check=True, stdout=_env.verbose_handle)
        sln_file = path.join(project_dir, custom_build_tool["path to .sln"])
        assert(path.exists(sln_file))
    else:
        assert cmake_generator in VS_CMAKE_GENERATORS, f"unknown cmake generator '{cmake_generator}'"
        gen_description = VS_CMAKE_GENERATORS[cmake_generator]
        project_dir = build_dir
        sln_file = invoke_cmake(build_dir, gen_description, project.get("cmake options"), project.get("cmake env"), project.get("cmake dir", ".."), project.get("required dependencies"))
        build_step = project.get("build step")
        if build_step:
            if isinstance(build_step, list):
                with cwd(build_dir):
                    for step in build_step:
                        subprocess.run(step.split(), check=True, stdout=_env.verbose_handle)
            elif isinstance(build_step, str) and build_step.endswith(".py"):
                build_step_full_path = os.path.realpath(build_step)
                with cwd(build_dir):
                    subprocess.run(["python", build_step_full_path], check=True, stdout=_env.verbose_handle)
            else:
                raise Exception("unknown build step format, should be list[str] or path to python script")

    generate_settings(project.get("to skip")).write(sln_file + ".DotSettings")
    return project_dir, sln_file


def duration(start, end):
    minutes, seconds = divmod(end - start, 60)
    return "{:02}:{:02}".format(int(minutes), int(seconds))


@contextmanager
def cwd(path):
    old_path = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_path)


def parse_projects(specified_projects: List[str]):
    if not specified_projects:
        for project_name in projects.keys():
            yield project_name, None
    else:
        for project in specified_projects:
            if ':' in project:
                yield project.split(':', 1)
            else:
                yield project, None


def create_parents(path: str):
    dir_name = os.path.dirname(os.path.realpath(path))
    os.makedirs(dir_name, exist_ok=True)


argparser = ArgumentParser()
argparser.add_argument("-p", "--project", dest="project", nargs='+', type=str)
argparser.add_argument("-e", "--env", dest='env_path')
argparser.add_argument('--build-dir', dest='build_directory')
argparser.add_argument('--vcpkg-dir', dest='vcpkg_directory')
argparser.add_argument('--projects-cache', dest='projects_cache_directory')
argparser.add_argument('--supported-generators', dest='supported_generators', nargs='*', type=str)
argparser.add_argument('--ci', action='store_true', dest='is_ci')
argparser.add_argument('--verbose', action='store_true', dest='verbose')
argparser.add_argument('--x86', action='store_true', dest='is_x86')
