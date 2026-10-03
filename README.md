# iclass-mcp

An MCP (Model Context Protocol) server for the Tamkang University (TKU) **iClass** (TronClass) learning platform.

Connect AI assistants (Claude Desktop, OpenAI Codex / ChatGPT Desktop, Cursor, and other MCP clients) directly to your iClass account to check pending assignments, track deadlines, browse courses and announcements, interact with forum discussions, manage files, and submit homework.

---

## Features

- 📅 **Todos & Deadlines**: Fetch upcoming and pending homework, quizzes, and exams with due dates.
- 📚 **Courses & Syllabi**: View ongoing enrolled courses, syllabus structures, and detailed learning activities.
- 📢 **Announcements**: Read course-level and campus-wide bulletins and notices.
- 💬 **Discussion Forums**: Browse categories, read topics/replies, create new discussion threads, post replies, and like topics.
- 📁 **Cloud Files**: Access your personal iClass cloud storage, upload local files, and download course materials.
- 📝 **Assignments & Progress**: Mark learning materials as read and submit homework directly.

---

## Installation & Setup

### Prerequisites

- Python 3.10 – 3.13
- A valid TKU SSO account (Student ID and SSO password)

### 1. Clone the repository

```bash
git clone https://github.com/GGQQmax/iclass-mcp.git
cd iclass-mcp
```

### 2. Configure Environment Variables

Copy the template file to `.env`:

```bash
cp .env.template .env
```

Edit `.env` with your student credentials:

```ini
USERNAMEID="YOUR_STUDENT_ID"
PASSWORD="YOUR_SSO_PASSWORD"
```

### 3. Create Virtual Environment & Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Client Configuration

### Codex / ChatGPT Desktop

The repository includes a project-scoped Codex configuration at `.codex/config.toml`. Update the absolute path to your environment:

```toml
[mcp_servers.iclass]
command = "/absolute/path/to/iclass-mcp/.venv/bin/python"
args = ["iclass_mcp_server.py"]
cwd = "/absolute/path/to/iclass-mcp"
default_tools_approval_mode = "prompt"
```

Open the repository folder in ChatGPT Desktop / Codex and trust the project when prompted.

Alternatively, register the server via the Codex CLI:

```bash
codex mcp add iclass -- /absolute/path/to/iclass-mcp/.venv/bin/python /absolute/path/to/iclass-mcp/iclass_mcp_server.py
```

### Claude Desktop

Add the server to your `claude_desktop_config.json` (located at `~/.config/Claude/claude_desktop_config.json` on Linux, or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "iclass": {
      "command": "/absolute/path/to/iclass-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/iclass-mcp/iclass_mcp_server.py"],
      "cwd": "/absolute/path/to/iclass-mcp"
    }
  }
}
```

### Cursor & Other MCP Clients (stdio)

- **Command**: `/absolute/path/to/iclass-mcp/.venv/bin/python`
- **Args**: `["/absolute/path/to/iclass-mcp/iclass_mcp_server.py"]`
- **Working Directory**: `/absolute/path/to/iclass-mcp`

---

## Available MCP Tools

| Tool | Description | Key Parameters |
| :--- | :--- | :--- |
| `get_todos` | Fetch pending homework, quizzes, and exams | None |
| `get_courses` | Get list of ongoing enrolled courses | None |
| `get_bulletins` | Fetch course or campus bulletins / announcements | `org_mode`, `page`, `size`, `course_ids` |
| `get_course_activities` | Fetch learning activities and syllabus structure | `course_id` |
| `get_activity_detail` | Fetch details for a specific activity | `activity_id` |
| `read_activity` | Mark an activity or resource upload as read | `activity_id`, `upload_id`, `course_id` |
| `get_enrollments` | List enrolled members/students for a course | `course_id` |
| `get_topic_categories` | Get discussion forum categories for a course | `course_id` |
| `get_topic` | Get details and replies for a discussion topic | `topic_id`, `course_id` |
| `reply_topic` | Post a reply to a discussion topic | `topic_id`, `content`, `uploads`, `course_id` |
| `create_topic` | Create a new discussion thread | `category_id`, `title`, `content`, `uploads`, `course_id` |
| `like_topic` | Like a discussion topic | `topic_id`, `course_id` |
| `get_my_files` | List personal cloud drive / uploaded resources | `page`, `size` |
| `upload_file` | Upload a local file to iClass personal drive | `file_path` |
| `download_file_by_reference` | Download a file by reference ID to `~/Downloads` | `reference_id` |
| `submit_homework` | Submit homework assignment with uploaded file IDs | `activity_id`, `upload_ids` |

---

## License

This project is licensed under the [Beerware License](License).
