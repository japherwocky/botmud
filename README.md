# QuickMUD - A Modern ROM 2.4 Python Port

[![Version](https://img.shields.io/badge/version-2.15.3-blue.svg)](https://github.com/japherwocky/botmud)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

QuickMUD is a modern Python port of the ROM 2.4b6 MUD engine, derived from ROM 2.4b6, Merc 2.1, and DikuMUD. This is a complete rewrite that brings the classic text-based MMORPG experience to modern Python with async networking and JSON world data. The engine is feature-complete and playable — all 255 ROM commands, combat, spells, and world systems are implemented and tested.

## What is a MUD?

A "[Multi-User Dungeon](https://en.wikipedia.org/wiki/MUD)" (MUD) is a text-based MMORPG that runs over telnet. ROM is renowned for its fast-paced combat system and rich player interaction. ROM was also the foundation for [Carrion Fields](http://www.carrionfields.net/), one of the most acclaimed MUDs ever created.

## Key Features

- **Feature-complete**: All 255 ROM commands implemented; combat, spells, skills, shops, and mob programs fully functional
- **Modern Python Architecture**: Fully async/await networking with SQLAlchemy ORM
- **Multiple Connection Options**: Telnet, WebSocket, and SSH server support
- **JSON World Loading**: Easy-to-edit world data with 352+ room resets
- **Complete Shop System**: Buy, sell, and list items with working economy
- **ROM Combat System**: Classic ROM combat mechanics and skill system
- **Social Features**: Say, tell, shout, and 100+ social interactions
- **Admin Commands**: Teleport, spawn, ban management, and OLC building
- **Comprehensive Testing**: 6,000+ passing tests across unit and integration suites

## Installation

### For Players & Server Operators

```bash
pip install quickmud
```

### Quick Start

Run a QuickMUD server:

**Telnet Server (port 5001):**
```bash
python3 -m mud socketserver
# or
mud socketserver
```

**WebSocket Server (port 8000):**
```bash
python3 -m mud websocketserver
# or
mud websocketserver
```

**SSH Server (port 2222):**
```bash
python3 -m mud sshserver
# or
mud sshserver
```

**All Three in One Process:**
```bash
python3 -m mud multiserver
# or
mud multiserver
# or, if you set up the Makefile:
make multi
```

Connect to the server:

**Via Telnet:**
```bash
telnet localhost 5001
```

**Via SSH:**
```bash
ssh -p 2222 player@localhost
# Note: SSH username/password are ignored; MUD authentication happens after connection
```

## Web Interface

QuickMUD includes a WebSocket server. The browser interface lives in a separate companion project so this engine repo can remain the canonical backend.

Recommended layout:

```text
~/dev/projects/
  botmud/
  quickmud-web-client/
```

The browser client should connect to:

```text
ws://127.0.0.1:8000/ws
```

### Browser Client Setup

From the companion `quickmud-web-client` repo:

```bash
cd ~/dev/projects/quickmud-web-client
npm install
npm run dev:all
```

That workflow starts this QuickMUD engine's WebSocket server, starts the frontend development server, and opens the browser client against the local `/ws` endpoint.

### Companion Repo

The web interface lives in a separate repository:
**[`quickmud-web-client`](https://github.com/Nostoi/quickmud-web-client)**

## For Developers

### Development Installation

```bash
git clone https://github.com/japherwocky/botmud.git
cd botmud
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .[dev]
```

### Running Tests

```bash
pytest  # Run the full suite
pytest tests/integration/ -v  # Run the integration suite
```

### Development Server

```bash
python -m mud  # Start development server
```

## Architecture

- **Async Networking**: Modern async/await with Telnet, WebSocket, and SSH servers
- **SQLAlchemy ORM**: Robust database layer with migrations
- **JSON World Data**: Human-readable area files with full ROM compatibility
- **Modular Design**: Clean separation of concerns (commands, world, networking)
- **Type Safety**: Comprehensive type hints throughout codebase

### Python Modules

Game systems are implemented in:

- `mud/net` — asynchronous telnet and websocket servers
- `mud/game_loop.py` — tick-based update loop
- `mud/commands` — command dispatcher and handlers
- `mud/combat` and `mud/skills` — combat and abilities
- `mud/account/` and `mud/db/` — character persistence and account state

### Docker

Build and run with Docker:

```bash
docker build -t quickmud .
docker run -p 5001:5001 quickmud
```

Or use docker-compose:

```bash
docker-compose up
```

Connect via telnet:

```bash
telnet localhost 5001
```

## Project Status

**Version**: 2.15.3
**Playability**: Feature-complete and running. All 255 ROM commands, combat, spells, skills, movement, shops, mob programs, OLC building, and admin tools are implemented and tested. You can run a server and play today.
**Compatibility**: Python 3.10+, cross-platform

### Implemented Systems

- Combat Engine with THAC0 and damage calculations
- Skills & Spells with ROM-faithful formulas
- Character System with classes, races, advancement, and equipment
- World System with area loading, room resets, mob/object spawning
- Shop Economy with pricing formulas and inventory management
- Communication systems: say, tell, shout, channels, 100+ socials
- Mob Programs with complete trigger system
- OLC Building with area/room/mob/object/help editors
- Admin Tools: teleport, spawn, ban management, wiznet
- Networking: async telnet, WebSocket, and SSH servers

### Quality Metrics

- **Test Suite**: 6,000+ passing tests
- **Code Coverage**: Comprehensive unit and integration test layers
- **Type Safety**: Full type hints throughout codebase

## Documentation

- [User Guide](docs/USER_GUIDE.md) — Player and server operator documentation
- [Admin Guide](docs/ADMIN_GUIDE.md) — Administrator and immortal documentation
- [Builder Migration Guide](docs/BUILDER_MIGRATION_GUIDE.md) — For ROM builders transitioning to QuickMUD
- [Installation Guide](docs/installation.md)
- [Configuration](docs/configuration.md)
- [World Building](docs/world-building.md)

## Dependencies

For a fully reproducible environment, use the pinned requirements file:

```bash
pip install -r requirements.txt
```

To update dependencies:

```bash
pip-compile requirements.in
```

## Publishing

To release a new version to PyPI:

1. Update the version in `pyproject.toml`
2. Commit and tag:

```bash
git commit -am "release: v1.2.3"
git tag v1.2.3
git push origin main --tags
```

The GitHub Actions workflow will build and publish the package when the tag is pushed.

## Contributing

Contributions are welcome! Please submit pull requests or open issues.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
