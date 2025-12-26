# Iranian IP Routes for MikroTik

This repository contains MikroTik RouterOS scripts for managing Iranian IP addresses. The scripts are automatically updated on a daily basis using IP address data from the [ipverse/rir-ip](https://github.com/ipverse/rir-ip/tree/master/country/ir) repository, which serves as the authoritative source of truth for Iranian IP address ranges.

## Overview

This project provides ready-to-use MikroTik RouterOS scripts (`.rsc` files) that contain all Iranian IP address ranges. These scripts can be used for various purposes including:

- **Routing**: Direct traffic from/to Iranian IP addresses through specific gateways
- **Firewall Rules**: Create firewall rules based on Iranian IP ranges
- **Address Lists**: Maintain updated address lists for Iranian IP addresses
- **Traffic Management**: Apply QoS policies or traffic shaping for Iranian destinations

## Data Source

The IP address data is sourced from [ipverse/rir-ip](https://github.com/ipverse/rir-ip), a comprehensive repository that aggregates Regional Internet Registry (RIR) data. This ensures that the IP ranges are:

- **Accurate**: Based on official RIR allocations
- **Up-to-date**: Updated regularly to reflect the latest allocations
- **Reliable**: Sourced from authoritative internet registry data

The scripts in this repository are automatically synchronized daily to ensure you always have the latest Iranian IP address ranges.

## Usage

### Importing the Script

To use these scripts on your MikroTik router:

1. **Download the Script**: Download the `.rsc` script file from this repository
2. **Upload to MikroTik**: Upload the script file to your MikroTik router via FTP, Winbox, or WebFig
3. **Import the Script**: Run the script using one of the following methods:

   **Via Terminal:**
   ```
   /import file-name=ir-routes.rsc
   ```

   **Via Winbox:**
   - Go to Files menu and upload the `.rsc` file
   - Open New Terminal
   - Type: `/import ir-routes.rsc`

### Keeping Scripts Updated

Since IP address allocations change over time, it's recommended to:

- **Regularly Update**: Check this repository for updates (scripts are updated daily)
- **Automate Updates**: Set up an automated process to fetch and apply updates periodically
- **Monitor Changes**: Review the commit history to see what IP ranges have been added or removed

## Script Structure

The MikroTik scripts typically contain commands to:

- Add IP address ranges to address lists
- Create firewall rules
- Set up routing policies
- Configure NAT rules

Example structure:
```routeros
/ip firewall address-list
add address=5.22.0.0/16 list=IR-IPs
add address=5.23.0.0/16 list=IR-IPs
# ... more IP ranges
```

## Use Cases

### 1. Routing Iranian Traffic

Direct all traffic to Iranian IPs through a specific gateway:
```routeros
/ip route
add dst-address-list=IR-IPs gateway=192.168.1.1
```

### 2. Firewall Rules

Create firewall rules for Iranian IP ranges:
```routeros
/ip firewall filter
add chain=forward src-address-list=IR-IPs action=accept comment="Allow Iranian IPs"
```

### 3. Bandwidth Management

Apply QoS policies for Iranian destinations:
```routeros
/queue tree
add name=IR-Traffic packet-mark=IR-packets parent=global
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
