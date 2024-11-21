import csv
from netmiko import ConnectHandler

# Define the switch credentials and connection parameters
switch = {
    'device_type': 'cisco_ios',  # or 'cisco_ios_telnet' for Telnet
    'host': '192.168.100.100',  # replace with your switch IP
    'username': 'cisco',  # your switch username
    'password': '123',  # your switch password
    'secret': 'cisco',  # enable password
    'session_log': 'session_log.txt',  # Enable session logging to file
}

# Function to handle port ranges and single ports
def handle_ports(ports, vlan_id, description, switch, is_management=False):
    #switch starts at 0 but csv file could start at 1
    switch = switch - 1
    if switch < 0:
        switch = 0
    config_commands = []
    
    # Split ports by commas
    for port in ports.split(','):
        if '-' in port:
            # Handle range of ports (e.g., 1-4)
            start_port, end_port = port.split('-')
            config_commands.append(f"interface range FastEthernet {switch}/{start_port} - {end_port}")
        else:
            # Handle single port
            config_commands.append(f"interface FastEthernet {switch}/{port}")
        
        # Handle trunk ports (based on description)
        if 'trunk' in description.lower() or 'uplink' in description.lower():
            config_commands.append(" switchport mode trunk")
            if vlan_id:
                config_commands.append(f" switchport trunk allowed vlan {vlan_id}")  # Apply VLAN filtering for trunk ports
        else:
            # For non-trunk ports (access ports)
            config_commands.append(f" switchport access vlan {vlan_id}")
            config_commands.append(f" description {description} port")
            if is_management:
                config_commands.append(" switchport mode access")
        
        config_commands.append(" no shutdown")
        config_commands.append("exit")  # Ensure clean exit
    return config_commands

# Define a function to process the CSV data and generate configuration commands
def generate_config(csv_file):
    config_commands = []
    ip_routing_needed = False  # Flag to track if IP routing is needed

    # Open the CSV file and read it
    with open(csv_file, mode='r') as file:
        reader = csv.DictReader(file, delimiter=';')

        for row in reader:
            vlan_id = row['Vlan']
            description = row['Description']
            ip_address = row['IP Address']
            subnet_mask = row['Netmask']
            ports = row['Ports']
            switchNr = row['Switch']
            
            # Check if VLAN number goes above the standard VTP range of 1-1005
            if int(vlan_id) > 1005:
                config_commands.append("vtp mode transparent")

            # Add VLAN creation commands
            config_commands.append(f"vlan {vlan_id}")
            config_commands.append(f" name {description}")  # This may be omitted if not supported
            config_commands.append("exit")  # Exit VLAN configuration mode

            # Special case for Management VLAN
            if ip_address and (description.lower().startswith("management") or description.lower().startswith("mgmt")):
                ip_routing_needed = True
                config_commands.append(f"interface vlan{vlan_id}")
                config_commands.append(f" description {description} (Management VLAN)")
                config_commands.append(f" ip address {ip_address} {subnet_mask}")
                config_commands.append(" no shutdown")
                config_commands.append("exit")  # Exit interface configuration mode
                # Mark ports as part of the management VLAN
                port_commands = handle_ports(ports, vlan_id, description, int(switchNr), is_management=True)
            else:
                if ip_address:
                    # Layer 3 VLAN configuration
                    ip_routing_needed = True
                    config_commands.append(f"interface vlan{vlan_id}")
                    config_commands.append(f" description {description}")
                    config_commands.append(f" ip address {ip_address} {subnet_mask}")
                    config_commands.append(" no shutdown")
                    config_commands.append("exit")  # Exit interface configuration mode
                else:
                    # Layer 2 VLAN configuration
                    config_commands.append(f"! Skipping Layer 3 configuration for VLAN {vlan_id} (Layer 2 only)")
                
                # Check if ports are defined
                if ports:
                    port_commands = handle_ports(ports, vlan_id, description, int(switchNr))

            # Add port configuration commands
            config_commands.extend(port_commands)
            config_commands.append("")  # Empty line for readability

    # Enable IP routing if needed
    if ip_routing_needed:
        config_commands.insert(0, "ip routing")  # Add at the top of the configuration
        config_commands.append("! IP routing was enabled because Layer 3 VLANs are configured.")

    # Add commands to disable VLAN 1
    config_commands.append("interface vlan1")
    config_commands.append(" shutdown")
    config_commands.append("exit")
    config_commands.append("! VLAN 1 has been disabled")

    return config_commands

# Define a function to save the generated commands to a file
def save_config_to_file(config_commands, output_file):
    with open(output_file, mode='w') as file:
        for command in config_commands:
            file.write(command + '\n')
    print(f"Configuration commands saved to {output_file}")

# Main function to run the script
def main():
    # File paths
    csv_file = 'BST-C-Core-2.csv'  # Path to your CSV file
    output_file = 'switch_config.txt'  # Path to save the generated config file

    # Generate the configuration commands from CSV data
    config_commands = generate_config(csv_file)

    # Save the configuration commands to a file
    save_config_to_file(config_commands, output_file)

    # Connect to the switch using Netmiko and apply the configuration
    try:
        with ConnectHandler(**switch) as net_connect:
            net_connect.enable()  # Enter enable mode
            # Send configuration commands to the switch
            net_connect.send_config_set(config_commands, read_timeout=15)
            print("Configuration applied successfully to the switch.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()