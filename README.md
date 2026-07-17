# botmud - A Modern ROM 2.4 Python MUD

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

botmud is a Python MUD engine forked from [rom24-quickmud-python](https://github.com/Nostoi/rom24-quickmud-python), a port of the ROM 2.4b6 MUD engine (itself derived from ROM 2.4b6, Merc 2.1, and DikuMUD). It brings the classic text-based MMORPG experience to modern Python with async networking and JSON world data. The engine is feature-complete and playable — all 255 ROM commands, combat, spells, and world systems are implemented and tested.

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

## Getting Started

Clone the repository and install in a virtual environment:

```bash
git clone https://github.com/japherwocky/botmud.git
cd botmud
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .[dev]
```

### Running a Server

**Telnet Server (port 5001):**
```bash
python3 -m mud socketserver
```

**WebSocket Server (port 8000):**
```bash
python3 -m mud websocketserver
```

**SSH Server (port 2222):**
```bash
python3 -m mud sshserver
```

**All Three in One Process:**
```bash
python3 -m mud multiserver
# or, if you set up the Makefile:
make multi
```

### Connecting

**Via Telnet:**
```bash
telnet localhost 5001
```

**Via SSH:**
```bash
ssh -p 2222 player@localhost
# Note: SSH username/password are ignored; MUD authentication happens after connection
```

## Development

### Running Tests

```bash
pytest  # Run the full suite
pytest tests/integration/ -v  # Run the integration suite
```

### Dependencies

For a fully reproducible environment, use the pinned requirements file:

```bash
pip install -r requirements.txt
```

To update dependencies:

```bash
pip-compile requirements.in
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
docker build -t botmud .
docker run -p 5001:5001 botmud
```

Or use docker-compose:

```bash
docker-compose up
```

## Implemented Systems

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

## Documentation

- [User Guide](docs/USER_GUIDE.md) — Player and server operator documentation
- [Admin Guide](docs/ADMIN_GUIDE.md) — Administrator and immortal documentation
- [Builder Migration Guide](docs/BUILDER_MIGRATION_GUIDE.md) — For ROM builders transitioning to botmud
- [Installation Guide](docs/installation.md)
- [Configuration](docs/configuration.md)
- [World Building](docs/world-building.md)

## Contributing

Contributions are welcome! Please submit pull requests or open issues.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
