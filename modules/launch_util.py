import os
import importlib
import importlib.util
import subprocess
import sys
import re
import logging
import importlib.metadata
import packaging.version


logging.getLogger("torch.distributed.nn").setLevel(logging.ERROR)  # sshh...
logging.getLogger("xformers").addFilter(lambda record: 'A matching Triton is not available' not in record.getMessage())

re_requirement = re.compile(r"\s*([-_a-zA-Z0-9]+)\s*(?:==\s*([-+_.a-zA-Z0-9]+))?\s*")
re_req_local_file = re.compile(r"\S*/([-_a-zA-Z0-9]+)-([0-9]+).([0-9]+).([0-9]+)[-_a-zA-Z0-9]*([\.tar\.gz|\.whl]+)\s*")

python = sys.executable
default_command_live = (os.environ.get('LAUNCH_LIVE_OUTPUT') == "1")
index_url = os.environ.get('INDEX_URL', "https://pypi.tuna.tsinghua.edu.cn/simple")

modules_path = os.path.dirname(os.path.realpath(__file__))
script_path = os.path.dirname(modules_path)


def is_installed(package):
    try:
        spec = importlib.util.find_spec(package)
    except ModuleNotFoundError:
        return False

    return spec is not None


def run(command, desc=None, errdesc=None, custom_env=None, live: bool = default_command_live) -> str:
    if desc is not None:
        print(desc)

    run_kwargs = {
        "args": command,
        "shell": True,
        "env": os.environ if custom_env is None else custom_env,
        "encoding": 'utf8',
        "errors": 'ignore',
    }
    
    if not live:
        run_kwargs["stdout"] = run_kwargs["stderr"] = subprocess.PIPE

    result = subprocess.run(**run_kwargs)

    if result.returncode != 0:
        error_bits = [
            f"{errdesc or 'Error running command'}.",
            f"Command: {command}",
            f"Error code: {result.returncode}",
        ]
        if result.stdout:
            error_bits.append(f"stdout: {result.stdout}")
        if result.stderr:
            error_bits.append(f"stderr: {result.stderr}")
        raise RuntimeError("\n".join(error_bits))

    return (result.stdout or "")


def run_pip(command, desc=None, live=default_command_live):
    try:
        index_url_line = f' --index-url {index_url}' if index_url != '' else ''
        return run(f'"{python}" -m pip {command} --prefer-binary{index_url_line}', desc=f"Installing {desc}",
                   errdesc=f"Couldn't install {desc}", live=live)
    except Exception as e:
        print(e)
        print(f'CMD Failed {desc}: {command}')
        return None


met_diff = {}
def requirements_met(requirements_file):
    global met_diff

    met_diff = {}
    result = True
    with open(requirements_file, "r", encoding="utf8") as file:
        for line in file:
            if line.strip() == "":
                continue

            m = re.match(re_requirement, line)
            if m:
                package = m.group(1).strip()
                version_required = (m.group(2) or "").strip()
            else:
                m1 = re.match(re_req_local_file, line)
                if m1 is None:
                    continue
                package = m1.group(1).strip()
                if line.strip().endswith('.whl'):
                    package = package.replace('_', '-')
                version_required = f'{m1.group(2)}.{m1.group(3)}.{m1.group(4)}'
            
            #print(f'requirement:{package}, {version_required}')
            if version_required == "":
                continue

            try:
                version_installed = importlib.metadata.version(package)
            except Exception:
                result = False
                continue

            if packaging.version.parse(version_required) != packaging.version.parse(version_installed):
                met_diff.update({package:version_installed})
                print(f"Version mismatch for {package}: Installed version {version_installed} does not meet requirement {version_required}")
                result = False

    return result

