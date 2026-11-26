# FPG Lab

FPG Lab is a local NiceGUI workspace for floor-plan research using this
checkout's FPG Core. Browse the [experiment catalogue](docs/EXPERIMENTS.md)
for active experiments and [architecture](docs/ARCHITECTURE.md) for data
ownership and configuration.

## Setup

From `fpg-lab/`, install Python 3.11 or newer and run one of these scripts.

| Platform | Setup | Start |
| --- | --- | --- |
| Windows | `powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1` | `.venv/Scripts/python.exe run_lab.py` |
| Ubuntu | `bash scripts/setup_ubuntu.sh` | `.venv/bin/python run_lab.py` |

Setup installs Core from the parent checkout, preserves an existing `.env`,
verifies Core and explicitly migrates and seeds the configured SQLite database.
Stop an existing Lab process first. The default address is
`http://127.0.0.1:8080`. See [.env.example](.env.example) for settings.

Use the experiment index to open setup, **System configurations** to edit or
activate a profile, and **Templates** to edit reusable floor-plan requests.
From the Lab environment, `python -m scripts.run_experiment --help` lists
the headless P01 workflow options. For database commands and checks, see
[development](docs/DEVELOPMENT.md). See the [glossary](GLOSSARY.md) for Lab terms.
