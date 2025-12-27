# Iranian IP Routes for MikroTik

This repository contains MikroTik RouterOS scripts for managing Iranian IP addresses. The scripts are automatically updated on a daily basis using IP address data from the [ipverse/rir-ip](https://github.com/ipverse/rir-ip/tree/master/country/ir) repository, which serves as the authoritative source of truth for Iranian IP address ranges.

## Overview

This project provides ready-to-use MikroTik RouterOS scripts (`.rsc` files) that contain all Iranian IP address ranges. The scripts are split into two files for flexibility:

- **`iran_list.rsc`**: Manages firewall address lists for Iranian IPs
- **`iran_routes.rsc`**: Manages routing entries for Iranian IPs

These scripts can be used for various purposes including:

- **Routing**: Direct traffic from/to Iranian IP addresses through specific gateways (requires both scripts)
- **Firewall Rules**: Create firewall rules based on Iranian IP ranges (requires only iran_list.rsc)
- **Address Lists**: Maintain updated address lists for Iranian IP addresses
- **Traffic Management**: Apply QoS policies or traffic shaping for Iranian destinations

## Data Source

The IP address data is sourced from [ipverse/rir-ip](https://github.com/ipverse/rir-ip), a comprehensive repository that aggregates Regional Internet Registry (RIR) data. This ensures that the IP ranges are:

- **Accurate**: Based on official RIR allocations
- **Up-to-date**: Updated regularly to reflect the latest allocations
- **Reliable**: Sourced from authoritative internet registry data

The scripts in this repository are automatically synchronized daily to ensure you always have the latest Iranian IP address ranges.

## Usage

This repository provides two separate script files:
- **`iran_list.rsc`**: Updates the firewall address list with Iranian IP addresses
- **`iran_routes.rsc`**: Updates routing entries for Iranian IP addresses

### Basic Usage (Address List Only)

If you only need the address list for firewall rules, you can use just the `iran_list.rsc` file:

```routeros
# Download and import the address list
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_list.rsc" dst-path=iran_list.rsc
/import iran_list.rsc
```

### Advanced Usage (Routes)

If you want to route Iranian traffic through a specific gateway, you need to set up environment variables and use both scripts:

#### 1. Setup Environment Variables

Before importing the routes script, define the required environment variables:

```routeros
# Define your Gateway
/system script environment set irgw user=admin value="192.168.88.2"

# Define your Routing Table (e.g., "main" or "irtraffic")
/system script environment set irtable user=admin value="main"
```

Replace `192.168.88.2` with your desired gateway IP and `main` with your routing table name.

#### 2. Import Both Scripts

You can fetch and import the scripts directly from GitHub:

```routeros
# Update the Address List
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_list.rsc" dst-path=iran_list.rsc
/import iran_list.rsc

# Update Routes
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_routes.rsc" dst-path=iran_routes.rsc
/import iran_routes.rsc
```

**Note:** To update existing routing table or gateway, modify the environment variables before importing the routes:

```routeros
# Change routing table or gateway if needed
/system script environment set [find name=irtable] value="main"
/system script environment set [find name=irgw] value="10.0.0.1"

# Then import the routes
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_routes.rsc" dst-path=iran_routes.rsc
/import iran_routes.rsc
```

### Keeping Scripts Updated

Since IP address allocations change over time, it's recommended to periodically re-fetch and import the scripts. You can automate this process using MikroTik's scheduler:

```routeros
# Create a scheduler to update the scripts daily
/system scheduler add name="update-iran-ips" interval=1d on-event="/tool fetch url=\"https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_list.rsc\" dst-path=iran_list.rsc\r\n/import iran_list.rsc\r\n/tool fetch url=\"https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_routes.rsc\" dst-path=iran_routes.rsc\r\n/import iran_routes.rsc"
```

Or check this repository for updates manually:
- **Regularly Update**: Scripts are updated daily
- **Monitor Changes**: Review the commit history to see what IP ranges have been added or removed

## Script Structure

The repository contains two separate MikroTik scripts:

### 1. iran_list.rsc - Address List

This script manages the firewall address list:

```routeros
# Clean up existing address list
/ip firewall address-list remove [find list="IRAN_IPS"]
:delay 5s

# Add IP ranges to address list
/ip firewall address-list add list=IRAN_IPS address=5.22.0.0/16
/ip firewall address-list add list=IRAN_IPS address=5.52.0.0/16
# ... more IP ranges
```

### 2. iran_routes.rsc - Routes

This script manages the routing entries using environment variables `$irgw` (gateway) and `$irtable` (routing table):

```routeros
# Clean up existing routes
/ip route remove [find comment="IR_BGP_DATA" routing-table=$irtable]
:delay 5s

# Add routes for IP ranges
/ip route add dst-address=5.22.0.0/16 gateway=$irgw routing-table=$irtable comment="IR_BGP_DATA"
/ip route add dst-address=5.52.0.0/16 gateway=$irgw routing-table=$irtable comment="IR_BGP_DATA"
# ... more routes
```

Both scripts automatically clean up previous entries before adding new ones to prevent duplicates.

## Use Cases

### 1. Address List Only (For Firewall Rules)

If you only need to identify Iranian IPs in firewall rules without routing:

```routeros
# Import only the address list
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_list.rsc" dst-path=iran_list.rsc
/import iran_list.rsc

# Use in firewall rules
/ip firewall filter
add chain=forward src-address-list=IRAN_IPS action=accept comment="Allow Iranian IPs"
add chain=forward dst-address-list=IRAN_IPS action=accept comment="Allow to Iranian IPs"
```

### 2. Routing Through a Specific Gateway

To route all Iranian IP traffic through a specific gateway:

```routeros
# Set your gateway and routing table
/system script environment set irgw user=admin value="192.168.88.2"
/system script environment set irtable user=admin value="main"

# Import both scripts
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_list.rsc" dst-path=iran_list.rsc
/import iran_list.rsc
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_routes.rsc" dst-path=iran_routes.rsc
/import iran_routes.rsc
```

### 3. Using with Custom Routing Tables

Route Iranian traffic through a separate routing table:

```routeros
# Define a custom routing table for Iranian traffic
/system script environment set irtable user=admin value="irtraffic"
/system script environment set irgw user=admin value="192.168.88.2"

# Import the scripts
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_list.rsc" dst-path=iran_list.rsc
/import iran_list.rsc
/tool fetch url="https://raw.githubusercontent.com/ehsan310/ir-mikrotik-routes/main/iran_routes.rsc" dst-path=iran_routes.rsc
/import iran_routes.rsc
```

## Requirements

- MikroTik RouterOS 6.x or 7.x
- Sufficient memory to handle the address lists (Iranian IP ranges can be extensive)
- Administrative access to the router

## Updates

This repository is automatically updated **daily** to reflect the latest Iranian IP address allocations. Each update:

- Pulls the latest data from ipverse/rir-ip
- Generates updated MikroTik scripts
- Commits the changes to this repository

Check the commit history to see the update frequency and changes.

## Contributing

If you encounter any issues or have suggestions for improvements:

1. Open an issue describing the problem or enhancement
2. Submit a pull request with your proposed changes
3. Ensure your changes maintain compatibility with MikroTik RouterOS

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Related Projects

- [ipverse/rir-ip](https://github.com/ipverse/rir-ip) - Source of IP address data
- [MikroTik RouterOS Documentation](https://wiki.mikrotik.com/) - Official MikroTik documentation

## Disclaimer

This project is not officially affiliated with MikroTik or any Regional Internet Registry. The IP address data is provided as-is, based on publicly available RIR data. Always verify critical routing configurations in your specific environment.

## Support

For questions or support:
- Open an issue in this repository
- Check MikroTik forums for RouterOS-specific questions
- Refer to the ipverse/rir-ip repository for data-related questions
