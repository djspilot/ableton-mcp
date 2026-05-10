# AbletonMCP - Ableton Live Model Context Protocol Integration
[![smithery badge](https://smithery.ai/badge/@ahujasid/ableton-mcp)](https://smithery.ai/server/@ahujasid/ableton-mcp)

AbletonMCP connects Ableton Live to Claude AI through the Model Context Protocol (MCP), allowing Claude to directly interact with and control Ableton Live. This integration enables prompt-assisted music production, track creation, and Live session manipulation.

### Join the Community

Give feedback, get inspired, and build on top of the MCP: [Discord](https://discord.gg/3ZrMyGKnaU). Made by [Siddharth](https://x.com/sidahuj)

## Features

- **Two-way communication**: Connect Claude AI to Ableton Live through a socket-based server
- **Track manipulation**: Create, modify, and manipulate MIDI and audio tracks
- **Instrument and effect selection**: Claude can access and load the right instruments, effects and sounds from Ableton's library
- **Clip creation**: Create and edit MIDI clips with notes
- **Session control**: Start and stop playback, fire clips, and control transport

## Components

The system consists of two main components:

1. **Ableton Remote Script** (`Ableton_Remote_Script/__init__.py`): A MIDI Remote Script for Ableton Live that creates a socket server to receive and execute commands
2. **MCP Server** (`server.py`): A Python server that implements the Model Context Protocol and connects to the Ableton Remote Script

## Installation

### Installing via Smithery

To install Ableton Live Integration for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@ahujasid/ableton-mcp):

```bash
npx -y @smithery/cli install @ahujasid/ableton-mcp --client claude
```

### Prerequisites

- Ableton Live 10 or newer
- Python 3.8 or newer
- [uv package manager](https://astral.sh/uv)

If you're on Mac, please install uv as:
```
brew install uv
```

Otherwise, install from [uv's official website][https://docs.astral.sh/uv/getting-started/installation/]

⚠️ Do not proceed before installing UV

### Claude for Desktop Integration

[Follow along with the setup instructions video](https://youtu.be/iJWJqyVuPS8)

1. Go to Claude > Settings > Developer > Edit Config > claude_desktop_config.json to include the following:

```json
{
    "mcpServers": {
        "AbletonMCP": {
            "command": "uvx",
            "args": [
                "ableton-mcp"
            ]
        }
    }
}
```

### Cursor Integration

Run ableton-mcp without installing it permanently through uvx. Go to Cursor Settings > MCP and paste this as a command:

```
uvx ableton-mcp
```

⚠️ Only run one instance of the MCP server (either on Cursor or Claude Desktop), not both

### Installing the Ableton Remote Script

[Follow along with the setup instructions video](https://youtu.be/iJWJqyVuPS8)

1. Download the `AbletonMCP_Remote_Script/__init__.py` file from this repo

2. Copy the folder to Ableton's MIDI Remote Scripts directory. Different OS and versions have different locations. **One of these should work, you might have to look**:

   **For macOS:**
   - Method 1: Go to Applications > Right-click on Ableton Live app → Show Package Contents → Navigate to:
     `Contents/App-Resources/MIDI Remote Scripts/`
   - Method 2: If it's not there in the first method, use the direct path (replace XX with your version number):
     `/Users/[Username]/Library/Preferences/Ableton/Live XX/User Remote Scripts`
   
   **For Windows:**
   - Method 1:
     C:\Users\[Username]\AppData\Roaming\Ableton\Live x.x.x\Preferences\User Remote Scripts 
   - Method 2:
     `C:\ProgramData\Ableton\Live XX\Resources\MIDI Remote Scripts\`
   - Method 3:
     `C:\Program Files\Ableton\Live XX\Resources\MIDI Remote Scripts\`
   *Note: Replace XX with your Ableton version number (e.g., 10, 11, 12)*

4. Create a folder called 'AbletonMCP' in the Remote Scripts directory and paste the downloaded '\_\_init\_\_.py' file

3. Launch Ableton Live

4. Go to Settings/Preferences → Link, Tempo & MIDI

5. In the Control Surface dropdown, select "AbletonMCP"

6. Set Input and Output to "None"

## Usage

### Starting the Connection

1. Ensure the Ableton Remote Script is loaded in Ableton Live
2. Make sure the MCP server is configured in Claude Desktop or Cursor
3. The connection should be established automatically when you interact with Claude

### Using with Claude

Once the config file has been set on Claude, and the remote script is running in Ableton, you will see a hammer icon with tools for the Ableton MCP.

## Capabilities

- Get session and track information
- Create and modify MIDI and audio tracks
- Create, edit, and trigger clips
- Control playback
- Load instruments and effects from Ableton's browser
- Add notes to MIDI clips
- Change tempo and other session parameters

## Example Commands

Here are some examples of what you can ask Claude to do:

- "Create an 80s synthwave track" [Demo](https://youtu.be/VH9g66e42XA)
- "Create a Metro Boomin style hip-hop beat"
- "Create a new MIDI track with a synth bass instrument"
- "Add reverb to my drums"
- "Create a 4-bar MIDI clip with a simple melody"
- "Get information about the current Ableton session"
- "Load a 808 drum rack into the selected track"
- "Add a jazz chord progression to the clip in track 1"
- "Set the tempo to 120 BPM"
- "Play the clip in track 2"


## Troubleshooting

- **Connection issues**: Make sure the Ableton Remote Script is loaded, and the MCP server is configured on Claude
- **Timeout errors**: Try simplifying your requests or breaking them into smaller steps
- **Have you tried turning it off and on again?**: If you're still having connection errors, try restarting both Claude and Ableton Live

## Technical Details

### Communication Protocol

The system uses newline-delimited JSON over a localhost TCP socket:

- Commands are sent as JSON objects with a `type` and optional `params`
- Responses are JSON objects with a `status` and `result` or `message`
- Each command and response is terminated with `\n`, which makes framing reliable for large responses

The MCP server connects to `127.0.0.1:9877` by default. Override this for development with:

```bash
ABLETON_MCP_HOST=127.0.0.1 ABLETON_MCP_PORT=9877 uvx ableton-mcp
```

### MCP Resources And Prompts

In addition to tools, the server exposes MCP resources for context:

- `ableton://session`
- `ableton://tracks`
- `ableton://transport`
- `ableton://scenes`
- `ableton://style-recipes`
- `ableton://command-log`
- `ableton://server-status`

Reusable MCP prompts are available for arrangement building, session diagnosis, and clip variation workflows.

### Arrangement Recording

The MCP server includes beat-timed performance helpers:

- `set_arrangement_position(beat)`
- `set_record_mode(enabled)`
- `start_arrangement_recording(start_beat)`
- `stop_arrangement_recording(stop_transport)`
- `perform_clip_sequence(events, record, realtime)`
- `perform_scene_sequence(sequence, record, realtime)`
- `preview_scene_arrangement_spec(spec)`
- `execute_scene_arrangement_spec(spec, dry_run)`
- `list_arrangement_presets()`
- `parse_arrangement_dsl(dsl, verbosity='compact')`
- `save_arrangement_plan(slot, spec)`
- `load_arrangement_plan(slot, verbosity='compact')`
- `patch_arrangement_plan(slot, patch, verbosity='compact')`
- `compose_arrangement(goal_prompt, dsl?, slot='current', mode='preview|execute', verbosity='compact')`

These tools are intended to perform Session View clips/scenes into Arrangement View. Real recording requires the updated Ableton Remote Script to be loaded in Live. Use `realtime=false` only for dry-run dispatch tests.

Recommended workflow for agents and skills:

1. Generate a compact DSL string like `style=ukg; bpm=138; template=club44; scenes=A,B,C,D; kit=909a; bass=reese2`.
2. Convert it with `parse_arrangement_dsl` and save to a slot with `save_arrangement_plan`.
3. Apply small updates with `patch_arrangement_plan` (e.g. `section[2].bars=8`, `swap scene A->C`) instead of resending full JSON.
4. Validate with `preview_scene_arrangement_spec`, then run `execute_scene_arrangement_spec`.
5. For one-shot flow, use `compose_arrangement` and keep `verbosity='compact'` for token-efficient responses.

### Development And Tests

```bash
uv run pytest
uv run python -m py_compile MCP_Server/server.py MCP_Server/protocol.py MCP_Server/music.py MCP_Server/recipes.py MCP_Server/arrangement.py AbletonMCP_Remote_Script/__init__.py
```

### Limitations & Security Considerations

- Creating complex musical arrangements might need to be broken down into smaller steps
- The tool is designed to work with Ableton's default devices and browser items
- Always save your work before extensive experimentation
- Keep the Remote Script socket bound to localhost unless you are intentionally developing a trusted remote setup

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This is a third-party integration and not made by Ableton.
