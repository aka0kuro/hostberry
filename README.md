# HostBerry

HostBerry is a lightweight, efficient network management system designed for Raspberry Pi and Linux servers. Built with **Go** (Golang) and **Lua**, it offers a fast web interface for managing system settings, network configurations, VPNs, and more.

## Features

- **System Management**: Monitor CPU, memory, disk usage, uptime, and manage power state.
- **Network Configuration**: Manage static IPs, DHCP server, and DNS settings.
- **WiFi Management**: Scan and connect to WiFi networks (Client mode) or create a Hotspot (AP mode).
- **Security**:
  - **VPN**: OpenVPN and WireGuard management.
  - **AdBlock**: DNS-level ad blocking (Pi-hole style).
  - **Firewall**: Integration with UFW.
- **Lua Scripting**: Extensible backend logic using Lua scripts for system interactions.
- **Responsive UI**: Modern, dark-themed web interface with mobile support.
- **Multi-language**: Support for English and Spanish.

## Architecture

- **Backend**: Go (Fiber framework) - High performance, single binary.
- **Logic**: Lua scripts - Flexible system interaction without recompiling.
- **Frontend**: HTML/CSS/JS (embedded in the Go binary).
- **Database**: SQLite (embedded) for storing configurations and logs.

## Installation

HostBerry is designed to be installed as a systemd service.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/aka0kuro/Hostberry.git
   cd Hostberry
   ```

2. **Run the installer**:
   ```bash
   sudo ./install.sh
   ```
   This script will:
   - Install dependencies (Go, Lua).
   - Compile the application.
   - Install systemd service (`hostberry.service`).
   - Configure permissions and firewall.

3. **Access the Web Interface**:
   - Open your browser and go to `http://<YOUR-IP>:8000`
   - Default credentials:
     - Username: `admin`
     - Password: `admin`
   - **Important**: Change your password immediately after logging in.

## Development

To modify the code:

1. Edit Go files (`*.go`) or Lua scripts (`lua/scripts/*.lua`).
2. Re-run `./install.sh` to recompile and restart the service.
   ```bash
   sudo ./install.sh
   ```

## License

MIT License
