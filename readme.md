# Mysh

## Overview

This document explains how `mysh` processes user input, handles environment variables, and executes pipelines, as well as provides an overview of the testing framework used.

## Translating User Input into Executable Commands

When a user enters a command, `mysh` processes it through the `run_command()` function. The flow of command translation is as follows:

1. **Pipeline Detection and Splitting**:
   - The `run_command()` function first checks if the input contains a pipe (`|`). If a pipe is detected, the input is split into separate commands using the `split_by_pipe_op()` function.
   - The `split_by_pipe_op()` function splits the command string by unquoted pipe operators and returns a list of individual commands. It ensures that commands enclosed within quotes are not split by the pipe operator.

2. **Variable Replacement**:
   - If no pipes are present, the command string undergoes variable substitution through the `replace_variables()` function (line 370). This function replaces all occurrences of `${VAR_NAME}` with their corresponding environment variable values, handling escaped variables to preserve them as literals.

3. **Command Execution**:
   - The command string is then parsed into arguments using `shlex.split()`. The `run_command()` function determines whether the command is built-in or external.
   - If the command matches any of the built-in commands (`var`, `cd`, `pwd`, `which`, `exit`), the corresponding handler function (e.g., `handle_cd_command()`) is invoked.
   - If the command is not built-in, it is passed to the `execute_external_command()` function, which searches the system's `PATH` to find and execute the command.

## Environment Variable Substitution and Escaping

Environment variables in `mysh` are managed through the `replace_variables()` function. This function performs the following steps:

1. **Pattern Matching**:
   - The function uses a regular expression to find patterns of the form `${VAR_NAME}` in the command string. These patterns are identified as potential environment variables that need to be replaced with their corresponding values.

2. **Variable Replacement**:
   - For each matched variable, the `replace()` function is called. It checks whether the variable name is valid using the `is_valid_variable_name()` function. If valid, the function retrieves the variable's value from `os.environ` and substitutes it into the command string.

3. **Escaping Variables**:
   - The function also handles cases where variables are escaped with a backslash (`\${VAR_NAME}`). If the preceding character is a backslash, the substitution is bypassed, and the original variable expression is retained as a literal string.

4. **Final Output**:
   - The modified command string, with all appropriate substitutions, is returned for further processing or execution.


## Pipeline Handling and Execution

Pipelines allow the output of one command to be used as the input for another. In `mysh`, pipelines are managed by the `execute_pipeline()` function. The execution flow for pipelines is as follows:

1. **Pipe Creation**:
   - For each pair of commands in the pipeline, a pipe is created using `os.pipe()`. Each pipe consists of a read and a write end that connects the commands.

2. **Process Forking**:
   - `mysh` forks a child process for each command in the pipeline. In each child process, `os.dup2()` is used to redirect the output (`stdout`) of the current command to the write end of the pipe, and the input (`stdin`) of the next command is redirected from the read end of the pipe.

3. **Command Execution**:
   - Each command is executed in its respective child process using `os.execvp()`, with the parent process waiting for all child processes to complete 

4. **Error Handling**:
   - The function includes robust error handling, ensuring that pipes are properly closed and processes are correctly managed.


## Testing Framework and Structure

The testing framework for `mysh` is designed to cover various aspects of shell functionality, including basic command execution, variable handling, pipelines, and error conditions. Test cases are organized into input/output pairs:

- **Input Files (`.in`)**: These files contain the exact commands a user would enter in `mysh`.
- **Output Files (`.out`)**: These files contain the expected output that `mysh` should produce when given the corresponding input file.

The `tests/` directory contains all test cases, including an end-to-end test that simulates a typical shell session with directory navigation, file operations, and command chaining. A `run_tests.sh` script automates the testing process by running each test case and comparing the actual output against the expected output. 

