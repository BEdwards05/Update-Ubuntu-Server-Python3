import subprocess
import sys
import socket

def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}. Please manually run: pip install {package}")
        sys.exit(1)

try:
    import argparse
except ImportError:
    install('argparse')
try:
    import paramiko
except ImportError:
    install('paramiko')

def write_and_print(f, message, verbosity, required_verbosity):
    if verbosity >= required_verbosity:
        print(message)
    if f is not None:
        f.write(message + '\n')

parser = argparse.ArgumentParser(description='Update and upgrade Ubuntu servers.')
parser.add_argument('-v', '--verbose', type=int, choices=[0, 1, 2], default=1, help='verbosity level: 0 (quiet), 1 (default), 2 (detailed)')
parser.add_argument('-s', '--servers', nargs='+', help='list of servers to update')
parser.add_argument('-o', '--output', nargs='?', help='output to file (provide file path as argument)')
parser.add_argument('-u', '--username', required=True, help='username for server authentication')
parser.add_argument('-p', '--password', help='password for server authentication')
parser.add_argument('-sp', '--sudo_password', required=True, help='sudo password for server')
parser.add_argument('-k', '--sshkey', nargs='?', help='private ssh key for server authentication')
args = parser.parse_args()

servers = args.servers if args.servers else ['10.10.10.10', '10.10.10.79', '10.10.10.220', '10.10.10.80', '10.10.10.247', '10.10.10.207', '10.10.10.121', '10.10.10.160']

f = None
if args.output:
    f = open(args.output, 'w')

for server in servers:
    try:
        write_and_print(f, f'Connecting to {server}', args.verbose, 1)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if args.sshkey:
            private_key = paramiko.RSAKey.from_private_key_file(args.sshkey)
            ssh.connect(server, username=args.username, pkey=private_key)
        else:
            ssh.connect(server, username=args.username, password=args.password)

        write_and_print(f, f'Connected to {server}, starting update and upgrade', args.verbose, 1)

        stdin, stdout, stderr = ssh.exec_command('sudo DEBIAN_FRONTEND=noninteractive apt-get update -y', get_pty=True)
        stdin.write(args.sudo_password + '\n')  # provide sudo password
        stdin.flush()

        stdout.channel.shutdown_write()
        output = stdout.readlines()

        for line in output:
            if args.sudo_password not in line.strip():  # do not print or log the sudo password
                write_and_print(f, line.strip(), args.verbose, 2)

        err_output = stderr.readlines()
        for line in err_output:
            write_and_print(f, f"Error: {line.strip()}", args.verbose, 1)

        stdin, stdout, stderr = ssh.exec_command('sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y', get_pty=True)
        stdin.write(args.sudo_password + '\n')  # provide sudo password
        stdin.flush()

        stdout.channel.shutdown_write()
        output = stdout.readlines()

        for line in output:
            if args.sudo_password not in line.strip():  # do not print or log the sudo password
                write_and_print(f, line.strip(), args.verbose, 2)

        err_output = stderr.readlines()
        for line in err_output:
            write_and_print(f, f"Error: {line.strip()}", args.verbose, 1)

        if any('upgraded,' in line for line in output):
            write_and_print(f, f'Packages were upgraded on {server}, rebooting', args.verbose, 1)
            ssh.exec_command('sudo reboot', get_pty=True)

        write_and_print(f, f'Finished updating {server}', args.verbose, 1)
        ssh.close()
    except paramiko.AuthenticationException:
        write_and_print(f, f'Authentication failed for {server}', args.verbose, 1)
        continue
    except paramiko.SSHException:
        write_and_print(f, f'Could not establish SSH connection for {server}', args.verbose, 1)
        continue
    except socket.timeout:
        write_and_print(f, f'Connection timed out for {server}', args.verbose, 1)
        continue

write_and_print(f, 'Finished updating all servers', args.verbose, 1)

if f is not None:
    f.close()
