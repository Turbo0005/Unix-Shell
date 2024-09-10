import os
import sys
import re
import json
import signal
import shlex
from parsing import split_by_pipe_op

logical_pwd = os.getcwd()


def setup_signals() -> None:
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)


def setup_default_environment():
    """
    Sets up default environment variables if they are not already defined.
    """
    if "PROMPT" not in os.environ:
        os.environ["PROMPT"] = ">> "

    if "MYSH_VERSION" not in os.environ:
        os.environ["MYSH_VERSION"] = "1.0"


def load_myshrc():
    """
    Load environment variables from .myshrc file if it exists.
    """
    # Check if MYSHDOTDIR is set, and use it as the base directory if it is
    base_dir = os.getenv("MYSHDOTDIR", os.path.expanduser("~"))
    rc_file_path = os.path.join(base_dir, ".myshrc")

    if os.path.exists(rc_file_path):
        try:
            with open(rc_file_path, 'r') as rc_file:
                variables = json.load(rc_file)

                for var_name, value in variables.items():
                    if not isinstance(value, str):
                        print(f"mysh: .myshrc: {var_name}: not a string", file=sys.stderr)
                        continue
                    if not re.match(r'^[a-zA-Z_]\w*$', var_name):
                        print(f"mysh: .myshrc: {var_name}: invalid characters for variable name", file=sys.stderr)
                        continue
                    os.environ[var_name], _ = replace_variables(value)

        except json.JSONDecodeError:
            print("mysh: invalid JSON format for .myshrc", file=sys.stderr)


def replace_variables(cmd: str) -> (str, bool):
    """
    Replaces variables in the command string with their environment variable values.
    Returns the modified command and a boolean indicating if the operation was successful.
    """

    def replace(match):
        var_name = match.group(1)
        if match.start() > 0 and cmd[match.start() - 1] == '\\':
            return match.group(0), True
        elif is_valid_variable_name(var_name):
            return os.environ.get(var_name, ""), True
        else:
            print(f"mysh: syntax error: invalid characters for variable {var_name}", file=sys.stderr)
            return None, False

    pattern = re.compile(r'\$\{([^}]+)\}')
    matches = pattern.finditer(cmd)

    success = True
    result = []
    last_end = 0

    for match in matches:
        replacement, valid = replace(match)
        if not valid:
            success = False
            return "", success
        if match.start() > 0 and cmd[match.start() - 1] == '\\':
            result.append(cmd[last_end:match.start() - 1])
            result.append(replacement)
        else:
            result.append(cmd[last_end:match.start()])
            result.append(replacement)
        last_end = match.end()

    result.append(cmd[last_end:])
    return ''.join(result), success


def is_valid_variable_name(var_name: str) -> bool:
    """
    Checks if the variable name is valid.
    A valid variable name starts with a letter or underscore, followed by letters, digits, or underscores.
    """
    return re.match(r'^[a-zA-Z_]\w*$', var_name) is not None


def handle_var_command(args):
    """
    Handle the var command.s
    """
    if len(args) <= 1:
        print(f"var: expected 2 arguments, got 0", file=sys.stderr)
        return
    include_sflag = 0
    if args[1].startswith('-'):
        if args[1] != '-s':
            print(f"var: invalid option: -{args[1][1]}", file=sys.stderr)
            return
        else:
            include_sflag = 1
    if len(args) - include_sflag > 3:
        print(f"var: expected 2 arguments, got {len(args) - include_sflag - 1}", file=sys.stderr)
        return
    var_name = args[1] if args[1] != '-s' else args[2]

    if not re.match(r'^[a-zA-Z_]\w*$', var_name):
        print(f"var: invalid characters for variable {var_name}", file=sys.stderr)
        return

    if include_sflag:
        try:
            result = execute_external_command(shlex.split(args[3]), capture_output=True)
            os.environ[var_name] = result
        except Exception as e:
            print(f"var: failed to execute command: {e}", file=sys.stderr)
    else:
        os.environ[var_name] = " ".join(args[2:])


def handle_cd_command(args):
    """
    Handle cd command.
    """
    global logical_pwd
    if len(args) > 2:
        print("cd: too many arguments", file=sys.stderr)
        return
    try:
        path = os.path.expanduser(args[1]) if len(args) > 1 else os.environ['HOME']

        if path == "-":
            path = os.environ.get("OLDPWD", logical_pwd)
            print(path)
        new_logical_pwd = os.path.abspath(os.path.join(logical_pwd, path))
        os.chdir(new_logical_pwd)
        logical_pwd = new_logical_pwd
        os.environ['PWD'] = logical_pwd

    except FileNotFoundError:
        print(f"cd: no such file or directory: {path}", file=sys.stderr)
    except NotADirectoryError:
        print(f"cd: not a directory: {path}", file=sys.stderr)
    except PermissionError:
        print(f"cd: permission denied: {path}", file=sys.stderr)


def handle_pwd_command(args):
    """
    Handle pwd command.
    """
    if len(args) > 1:
        for arg in args[1:]:
            if not arg.startswith('-'):
                print("pwd: not expecting any arguments", file=sys.stderr)
                return
            for option in arg[1:]:
                if option != 'P':
                    print(f"pwd: invalid option: -{option}", file=sys.stderr)
                    return

    print(os.path.realpath(os.getcwd()) if '-P' in args else logical_pwd)


def handle_which_command(args):
    """
    Handle which command.
    """
    if len(args) == 1:
        print("usage: which command ...", file=sys.stderr)
        return

    path_dirs = os.getenv("PATH", os.defpath).split(os.pathsep)

    def find_executable(command):
        if command in ['var', 'pwd', 'cd', 'which', 'exit']:
            return f"{command}: shell built-in command"

        for path_dir in path_dirs:
            executable_path = os.path.join(path_dir, command)
            if os.path.isfile(executable_path) and os.access(executable_path, os.X_OK):
                return executable_path
        return f"{command} not found"

    for cmd_name in args[1:]:
        result = find_executable(cmd_name)
        print(result)


def handle_exit_command(args):
    """
    Handle exit command.
    """
    if len(args) > 2:
        print("exit: too many arguments", file=sys.stderr)
        return
    if len(args) == 2:
        try:
            exit_code = int(args[1])
        except ValueError:
            print(f"exit: non-integer exit code provided: {args[1]}", file=sys.stderr)
            return
        sys.exit(exit_code)
    else:
        sys.exit(0)


def expand_path_in_args(args):
    """
    Expand "~" path.
    """
    return [os.path.expanduser(arg) if arg.startswith('~') else arg for arg in args]


def execute_external_command(args, capture_output=False):
    """
    Run non-built-in commands.
    """
    args = expand_path_in_args(args)

    # Check if the command exists
    command_path = None
    if '/' in args[0]:
        command_path = args[0] if os.path.isfile(args[0]) else None
    else:
        for path_dir in os.getenv("PATH", os.defpath).split(os.pathsep):
            potential_path = os.path.join(path_dir, args[0])
            if os.path.isfile(potential_path):
                command_path = potential_path
                break

    if command_path is None:
        print(f"mysh: command not found: {args[0]}", file=sys.stderr)
        return

    if not os.access(command_path, os.X_OK):
        print(f"mysh: permission denied: {args[0]}", file=sys.stderr)
        return

    try:
        if capture_output:
            read_fd, write_fd = os.pipe()
            child_pid = os.fork()

            if child_pid == 0:
                try:
                    os.setpgid(0, 0)
                except PermissionError:
                    pass

                os.close(read_fd)
                os.dup2(write_fd, sys.stdout.fileno())
                os.close(write_fd)
                os.execvp(args[0], args)
            else:
                os.close(write_fd)
                output = os.fdopen(read_fd).read()
                os.waitpid(child_pid, 0)
                return output
        else:
            child_pid = os.fork()

            if child_pid == 0:
                try:
                    os.setpgid(0, 0)
                except PermissionError:
                    pass

                os.execvp(args[0], args)
            else:
                os.waitpid(child_pid, 0)
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)


def execute_pipeline(commands):
    """
    Execute a pipeline of commands.
    """
    num_commands = len(commands)
    pipe_fds = []

    # Create pipes for all command pairs
    for _ in range(num_commands - 1):
        pipe_fds.append(os.pipe())

    pids = []

    for i, cmd in enumerate(commands):
        args = shlex.split(cmd)
        pid = os.fork()

        if pid == 0:
            if i > 0:
                os.dup2(pipe_fds[i - 1][0], sys.stdin.fileno())
            if i < num_commands - 1:
                os.dup2(pipe_fds[i][1], sys.stdout.fileno())
            execute_external_command(args)
            sys.exit(0)

        elif pid > 0:
            pids.append(pid)
            if i > 0:
                os.close(pipe_fds[i - 1][0])
            if i < num_commands - 1:
                os.close(pipe_fds[i][1])
        else:
            print("mysh: failed to fork process", file=sys.stderr)
            break
    for read_fd, write_fd in pipe_fds:
        try:
            os.close(read_fd)
            os.close(write_fd)
        except OSError:
            pass

    # Wait for all child processes to finish
    for pid in pids:
        os.waitpid(pid, 0)


def preprocess_command(cmd: str) -> str:
    """
    Preprocess the command string to replace escaped quotes with placeholders.
    """
    cmd = cmd.replace("\\'", "__SINGLE_QUOTE__")
    cmd = cmd.replace('\\"', "__DOUBLE_QUOTE__")
    return cmd


def postprocess_args(args: list) -> list:
    """
    Postprocess the list of arguments to replace placeholders with the original escaped quotes.
    """
    return [arg.replace("__SINGLE_QUOTE__", "'").replace("__DOUBLE_QUOTE__", '"') for arg in args]


def custom_split_command(cmd: str) -> (list, bool):
    """
    Custom function to preprocess, split using shlex, and postprocess the command.
    Returns a list of arguments and a boolean indicating if the operation was successful.
    """
    try:
        # Preprocess the command to replace escaped quotes with placeholders
        preprocessed_cmd = preprocess_command(cmd)
        lexer = shlex.shlex(preprocessed_cmd, posix=True)
        lexer.whitespace_split = True
        lexer.escape = '\\'
        args = list(lexer)
        args = postprocess_args(args)
        if lexer.state is not None and lexer.state in lexer.quotes:
            print("mysh: syntax error: unterminated quote", file=sys.stderr)
            return [], False

        return args, True

    except ValueError as e:
        # Handle specific errors related to shlex parsing
        if "No closing quotation" in str(e):
            print("mysh: syntax error: unterminated quote", file=sys.stderr)
        else:
            print(f"mysh: syntax error: {e}", file=sys.stderr)
        return [], False


def run_command(cmd: str) -> None:
    # Check if the command contains pipes
    if '|' in cmd:
        commands = split_by_pipe_op(cmd)
        for command in commands:
            if command.strip() == "":
                print("mysh: syntax error: expected command after pipe", file=sys.stderr)
                return
        execute_pipeline(commands)
    else:
        cmd, success = replace_variables(cmd)
        if not success:
            return
        args, success = custom_split_command(cmd)
        if not success:
            return

        if not args:
            return

        command_map = {
            'var': handle_var_command,
            'pwd': handle_pwd_command,
            'cd': handle_cd_command,
            'which': handle_which_command,
            'exit': handle_exit_command
        }

        if args[0] in command_map:
            command_map[args[0]](args)
        else:
            execute_external_command(args)


def run_shell() -> None:
    load_myshrc()  # Load the .myshrc file on startup
    while True:
        try:
            prompt = os.getenv("PROMPT", ">> ")
            cmd = input(prompt)

            if cmd.strip() == "":
                continue

            if not cmd:
                print()
                break

            run_command(cmd)

        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue


def main() -> None:
    setup_default_environment()
    setup_signals()
    run_shell()


if __name__ == "__main__":
    main()

