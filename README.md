# iclass-cli

View the to-do list, submit your homework, and achieve more in your terminal!

---

## Installation

### Prerequisites

- Python 3.10 and before 3.14*
- Python venv virtual environments

## Manually install

Git clone the project

```bash
git clone https://github.com/GGQQmax/iclass-mcp.git
```

### Environment variables set up

add `.env` to the project folder

```bash
USERNAMEID="YOURSTUDENTID"
PASSWORD="YOURSSOPASSWORD"
```
Set up python virtual environments and install package

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Use with Codex

Create the `.env` file described above and install the requirements. The repository includes a project-scoped Codex configuration at `.codex/config.toml`. Set its `command` and `cwd` to the absolute paths for your clone. For example, if the repository is at `/home/you/git/iclass-cli`:

```toml
[mcp_servers.iclass]
command = "/home/you/git/iclass-mcp/.venv/bin/python"
args = ["iclass_mcp_server.py"]
cwd = "/home/you/git/iclass-mcp"
default_tools_approval_mode = "prompt"
```

Open the repository in the ChatGPT desktop app and trust the project when prompted. Project-scoped MCP configuration is loaded only for trusted projects. The `prompt` approval setting asks before each tool call.

The `codex mcp add` and `codex mcp list` commands are an alternative for users who have installed the separate Codex CLI; they are not commands provided by the `chatgpt` desktop-app launcher.
