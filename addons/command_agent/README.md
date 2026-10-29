# Command Agent for Milky

Runs shell commands from Milky and, for larger requests, lets a small agent
run several commands, read their output, adjust, and report back.

The addon has two tools:

- `run_command` — run one non-interactive shell command and return its output
  and exit code. This is the fast path for a direct request such as
  "run `python main.py`".
- `run_task` — give the active chat model a self-contained task. The agent can
  inspect files, run a program, read an error, try another command, and then
  call `finish` with a summary. This is the multi-step path.

The tools are exposed to Milky as `addon__command_agent__run_command` and
`addon__command_agent__run_task`.

## Requirements

- Milky with an active AI provider whose model supports tool calls.
- Bash (preferred) or a POSIX shell on Linux/macOS, or `cmd.exe` on Windows.
- Python 3.10 or newer.

No extra Python packages are needed.

## Install

Install it from **Settings → Skills** using this repository URL:

```text
https://github.com/stepaandgddev/milky-pc-control
```

The repository root is the addon itself. You can also clone or copy it into
Milky's `addons/` directory:

```text
<Milky>/addons/command_agent/
```

The addon ships with an icon and no background processes.

After installing, open **Settings → Skills**, enable **Command Agent**, and
click **Reload skills**. A restart is not required.

## Examples

- "Run `python main.py` and tell me what happened."
- "Run the tests and summarize the failures."
- "Look at this project, run the app, and explain the traceback."
- "Check whether `ffmpeg` is installed and which version it is."
- "Run `pwd` in `~/Projects/my-app`."

For a direct command, Milky can use `run_command`. For a request that may need
more than one command, it should use `run_task`.

## How `run_task` works

```text
User task
   ↓
Agent model chooses a command
   ↓
Command runs, output and exit code are returned
   ↓
Agent reads the result and chooses the next command
   ↓
… repeat up to 4 steps by default …
   ↓
finish(summary) → Milky replies to the user
```

The agent only sees the task text, not the full chat history. Milky is expected
to pass a self-contained task with the relevant details.

## Safety

Commands run with the same permissions as Milky. There is no confirmation
dialog, so the user should only ask for commands they are willing to run.

The addon blocks obvious catastrophic and secret-exposing commands, including:

- `sudo` / `doas` and other elevated commands
- shutdown, reboot, power-off and suspend
- disk formatting, partitioning and raw writes to block devices
- recursive deletion of the filesystem root, the home directory, the current
  directory, or system directories
- `find / -delete` and world-writable root
- piping a download directly into a shell
- reading or copying `.env`, `settings.json`, SSH keys, cloud credentials and
  similar secret files
- dumping the whole process environment or `/proc/*/environ`
- killing PID 1

The agent is also instructed not to install packages, change credentials,
commit or push git changes, or send data anywhere unless the task explicitly
asks for it. These are guardrails, not a sandbox: a determined command can
still do damage. Use the addon only if you trust the model and the commands.

## Settings

The addon reads optional fields from its entry under
`addons.settings.command_agent`:

```json
{
  "working_directory": "/home/me/Projects/my-app",
  "timeout": 60,
  "max_steps": 4,
  "max_output_chars": 12000
}
```

- `working_directory` — default directory for commands. Relative paths are
  resolved against Milky's application directory.
- `timeout` — default per-command timeout in seconds (1–300).
- `max_steps` — default number of agent turns (1–8).
- `max_output_chars` — how much command output is kept (2,000–40,000). The
  middle is truncated when a command is very noisy.

All fields are optional. Restart Milky or reload skills after editing the
settings file.

## Behavior notes

- Each command starts a fresh shell. `cd` does not persist between calls; use
  the `cwd` argument instead. On Linux/macOS the addon uses `bash` when it is
  available, otherwise `$SHELL` or `/bin/sh`. On Windows it uses `cmd.exe`.
- Commands receive `stdin` closed, so interactive prompts fail instead of
  hanging. The process group is killed when the timeout expires, and any
  background children left in that group are cleaned up when the command ends.
  This addon is not a process manager; do not use it to keep servers running.
- Output is collected as UTF-8 with replacement characters, ANSI escapes are
  removed, and very large output keeps the beginning and end.
- Common API-key, bearer-token and `key=value` secret patterns are redacted
  from command output and reports before the model sees them.
- A timeout returns the partial output with an explicit timeout note.
- The addon does not commit, push, or modify git history by itself.
