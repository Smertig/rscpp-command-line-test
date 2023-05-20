import os
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


# assert 'VsInstallRoot' in os.environ, 'Missing VsInstallRoot environment variable'
# assert 'VCTargetsPath' in os.environ, 'Missing VCTargetsPath environment variable'


class Environment:
    def __init__(self, args):
        self._args = args
        if args.env_path:
            with open(args.env_path) as f:
                self._env = json.load(f)
        else:
            self._env = None

        self._build_directory = args.build_directory or self._get_env("build directory")
        self._projects_cache_directory = args.projects_cache_directory or self._get_env("projects cache dir")
        self._supported_generators = args.supported_generators or self._get_env("supported generators") or []
        self._vcpkg_directory = args.vcpkg_directory or self._get_env("vcpkg dir")
        self._verbose = args.verbose
        self._cli_test_dir = os.path.dirname(os.path.abspath(__file__))

        assert self._build_directory, 'Missing build directory'

    def _get_env(self, key: str) -> Optional[str]:
        if self._env is None:
            return None
        return self._env.get(key)

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
    def resharper_version(self) -> Optional[str]:
        return self._get_env("resharper version")

    @property
    def computer_name(self) -> Optional[str]:
        return self._get_env("computer name")

    @property
    def caches_home(self) -> str:
        return self._get_env("caches home") or path.join(self.cli_test_dir, "caches-home")

    @property
    def projects_dir(self) -> str:
        return self._projects_cache_directory or path.join(self.cli_test_dir, "projects")

    @property
    def inspect_code_path_x86(self) -> str:
        return path.join(self.resharper_build, "inspectcode.x86.exe")

    @property
    def inspect_code_path_x64(self) -> str:
        return path.join(self.resharper_build, "inspectcode.exe")

    @property
    def verbose(self) -> bool:
        return self._verbose

    @property
    def verbose_handle(self) -> Optional[int]:
        return None if self.verbose else PIPE


# TODO: remove global vars completely
_env: Environment = None


def load_env(args):
    global _env
    _env = Environment(args)
    return _env


with open("projects.json") as f:
    projects = json.load(f)

with open("toolchains.json") as f:
    toolchains_info = json.load(f)


def git_clone_and_force_checkout_if_needed(target_dir, url, commit):
    if not path.exists(path.join(target_dir, ".git")):
        subprocess.run(["git", "clone", url, target_dir], check=True)

    with cwd(target_dir):
        subprocess.run(["git", "checkout", commit], check=True, stdout=PIPE, stderr=_env.verbose_handle)
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
            subprocess.run(custom_update_source_script, check=True, stdout=PIPE)

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


def invoke_cmake(build_dir, cmake_generator, cmake_options, required_dependencies):
    cmd_line_args = ["cmake", "..", "-G", cmake_generator["name"]]
    architecture = cmake_generator.get("architecture")
    if architecture:
        cmd_line_args.append("-A")
        cmd_line_args.append(architecture)
    if required_dependencies:
        vcpkg_dir = _env.vcpkg_dir
        if vcpkg_dir:
            with cwd(vcpkg_dir):
                subprocess.run(["vcpkg", "install"] + required_dependencies + ["--triplet", toolchains_info["vcpkg"]["triplet"]], check=True, stdout=_env.verbose_handle)
                cmd_line_args.append("-DCMAKE_TOOLCHAIN_FILE={0}/scripts/buildsystems/vcpkg.cmake".format(vcpkg_dir))
        else:
            raise Exception("project has required dependencies {0}, but environment doesn't containt path to vcpkg".format(required_dependencies))
    if cmake_options:
        cmd_line_args.extend(cmake_options)
    makedirs(build_dir, exist_ok=True)
    with cwd(build_dir):
        subprocess.run(cmd_line_args, check=True, stdout=_env.verbose_handle)
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
    args = ["--severity=ERROR", "-f=Xml", "-no-build", "-o=" + report_file, "--caches-home=" + _env.caches_home]
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

    log_file = path.join(project_dir, "resharper-logs.txt")
    err_file = path.join(project_dir, "resharper-logs.err.txt")
    if os.path.exists(log_file): os.remove(log_file)
    if os.path.exists(err_file): os.remove(err_file)
    args.append("--LogLevel=INFO")
    args.append("--LogFile=" + log_file)

    args.append(sln_file)
    return args, report_file


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
    target_dir = path.join(_env.projects_dir, project_name)
    project_dir = get_sources(project["sources"], target_dir, branch)

    fixup_sources = project.get("fixup sources")
    if isinstance(fixup_sources, list):
        with cwd(target_dir):
            exec("\n".join(fixup_sources), {}, {})
    elif isinstance(fixup_sources, str) and fixup_sources.endswith(".py"):
        full_path = os.path.realpath(fixup_sources)
        with cwd(target_dir):
            subprocess.run(["python", full_path], check=True, stdout=_env.verbose_handle)
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
        gen_description = toolchains_info["VS CMake Generators"][cmake_generator]
        build_dir = path.join(project_dir, project.get("build dir", "build") + "-" + cmake_generator)
        project_dir = build_dir
        sln_file = invoke_cmake(build_dir, gen_description, project.get("cmake options"), project.get("required dependencies"))
        build_step = project.get("build step")
        if build_step:
            with cwd(build_dir):
                for step in build_step:
                    subprocess.run(step.split(), check=True, stdout=_env.verbose_handle)

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
argparser.add_argument('--verbose', action='store_true', dest='verbose')
