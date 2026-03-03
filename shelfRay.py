import paramiko
import time
import re
import subprocess
import json

from parser import parse_ecm_cards, AMPLIFIER_REGISTRY

USERNAME = "admin"
PASSWORD = "CHGME.1a"
PROMPT_REGEX = re.compile(r"admin@.*?>")  # Accepts any prompt like admin@FSP3000C> or admin@ATL_SIT_2>
IP_N_ROW_REGEX = re.compile(r"(fe80::[\w:]+)%?\w*\s+dev\s+\w+\s+lladdr\s+([\da-f:]+)", re.IGNORECASE)

def fetch_cards_from_ecm(ip):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(ip, username=USERNAME, password=PASSWORD, timeout=10)
        chan = client.invoke_shell()
        time.sleep(0)

        output = chan.recv(4096).decode("utf-8")

        if "password:" in output.lower():
            chan.send(PASSWORD + "\n")
            time.sleep(0)
            output += chan.recv(4096).decode("utf-8")

        while not PROMPT_REGEX.search(output):
            chan.send("\n")
            time.sleep(0)
            output += chan.recv(4096).decode("utf-8")

        chan.send("show card\n")
        time.sleep(0)

        cmd_output = ""
        while not PROMPT_REGEX.search(cmd_output):
            time.sleep(0)
            cmd_output += chan.recv(4096).decode("utf-8")
        client.close()
        return parse_ecm_cards(cmd_output, ip)

    except Exception as e:
        print(f"❌ Failed to connect to {ip}: {e}")
        return []

def update_ecm_cards_with_ipv6(ecip, card_list) -> list:
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-p", "614",
                f"root@{ecip}",
                "ip n | grep P"
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        output = result.stdout
        for match in IP_N_ROW_REGEX.finditer(output):
            ipv6 = match.group(1)
            card_name, card_slot = card_name_slot_from_ipv6(ecip=ecip, ccip=ipv6)
            if not card_name or not card_slot:
                continue
            matched = False
            for card in card_list:
                if (
                    card.get("name", "").upper() == card_name.upper() and
                    str(card.get("slot")) == card_slot
                ):
                    card["ipv6"] = ipv6
                    matched = True
                    # print(f"✅ Matched and updated card {card_name}:{card_slot} with IPv6 {ipv6}")
                    break

            if not matched:
                print(f"⚠️ No matching card found in list for {card_name}:{card_slot} ({ipv6})")

        return card_list

    except subprocess.CalledProcessError as e:
        print(f"❌ SSH to {ecip} failed: {e.stderr.strip()}")
        return []

PS1_REGEX = re.compile(r"(?P<name>[A-Z0-9\-]+):(?P<slot>\d+)\.\d+")

def card_name_slot_from_ipv6(ecip, ccip) -> tuple[str, str]:
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-p", "614",
                f"root@{ecip}",
                f"ssh {ccip}%mgmt \"bash -i -c 'echo \\$PS1'\""
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        output_lines = result.stdout.strip().splitlines()

        # Get only the line that contains the actual PS1 string
        for line in output_lines:
            if '\\[' in line and ':' in line:
                ps1_output = line.strip()
                break
        else:
            print(f"⚠️ No usable PS1 line found in:\n{result.stdout}")
            return None, None

        match = PS1_REGEX.search(ps1_output)
        if match:
            card_name = match.group("name")
            if card_name not in AMPLIFIER_REGISTRY.keys():
                return None, None
            slot = match.group("slot")
            print(f"🔍 Found card: {card_name}, slot: {slot}")
            return card_name, slot
        else:
            print(f"⚠️ Could not parse card info from PS1: {ps1_output}")
            return None, None

    except subprocess.CalledProcessError as e:
        print(f"❌ SSH chain to {ccip}%mgmt via {ecip} failed:\n{e}")
        return None, None

def fetch_nodes(ip_list: list[str]) -> dict:
    nodes = {}
    for ip in ip_list:
        nodes[ip] = fetch_cards_from_ecm(ip=ip)

    for ecip, card_list in nodes.items():
        updated_cards = update_ecm_cards_with_ipv6(ecip=ecip, card_list=card_list)
        nodes[ecip] = updated_cards
    return nodes

WT_PATH = "/mnt/c/Users/jsebek/AppData/Local/Microsoft/WindowsApps/wt.exe"
def launch_ecm_terminal(ecm_ip: str, port: str = 22):
    try:
        subprocess.run(
            ["ssh-keygen", "-f", "/home/jsebek/.ssh/known_hosts", "-R", ecm_ip],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to remove key from known hosts for {ecm_ip}: {e}")

    title = f"ECM .{ecm_ip.split('.')[-1]}"
    if port == 614:
        ssh_cmd = f"ssh -tt -o StrictHostKeyChecking=no -p 614 root@{ecm_ip}"
    else:
        ssh_cmd = f"sshpass -p 'CHGME.1a' ssh -tt -o StrictHostKeyChecking=no -p 22 admin@{ecm_ip}"

    cmd = [
        WT_PATH,
        "new-tab",
        "--title", title,
        "wsl",
        "-d",
        "Ubuntu",
        "--",
        "bash",
        "-l",
        "-c",
        ssh_cmd
    ]

    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print(f"❌ Failed to launch ECM CLI: {e}")

def launch_cc3_cli(ecm_ip: str, cc_ipv6: str, card_name: str, slot: str = ""):
    # Label tab with ECM short IP and slot if available
    title = f"{card_name} (.{ecm_ip.split('.')[-1]}/{slot})" if slot else f"{card_name} {ecm_ip}"

    try:
        subprocess.run(
            ["ssh-keygen", "-f", "/home/jsebek/.ssh/known_hosts", "-R", ecm_ip],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to remove key from known hosts for {ecm_ip}: {e}")


    # SSH chain with forced TTY allocation on CC3 side only
    ssh_chain = f"ssh -tt -o StrictHostKeyChecking=no -p 614 root@{ecm_ip} 'ssh {cc_ipv6}%mgmt'"

    cmd = [
        WT_PATH,
        "new-tab",
        "--title", title,
        "wsl",
        "-d",
        "Ubuntu",
        "--",
        "bash",
        "-l",
        "-c",
        ssh_chain
    ]

    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print(f"❌ Failed to launch CC3 CLI: {e}")

def serial(term_server: str, term_port: str, card_name: str, ecm_ip: str, slot: str = ""):
    # Label tab with ECM short IP and slot if available
    title = f"Serial {card_name} (.{ecm_ip.split('.')[-1]}/{slot})" if slot else f"{card_name} {ecm_ip}"

    # SSH chain with forced TTY allocation on CC3 side only
    ssh_cmd = f"telnet {term_server} {term_port}"

    cmd = [
        WT_PATH,
        "new-tab",
        "--title", title,
        "wsl",
        "--",
        "bash",
        "-l",
        "-c",
        ssh_cmd
    ]

    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print(f"❌ Failed to launch CC3 CLI: {e}")

def deploy(deploy_cmd: str):
    cmd = [
        WT_PATH,
        "new-tab",
        "--title", "Deploying Packages",
        "wsl",
        "-d",
        "Ubuntu",
        "--",
        "bash",
        "-l",
        "-c",
        f"{deploy_cmd}"
    ]
    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print(f"❌ Failed to launch CC3 CLI: {e}")

# replacing with devploy
def install_cc(install_cc_cmd: str, ecm_ip: str, card_name: str, slot: str = ""):
    title = f"Install_cc {card_name} (.{ecm_ip.split('.')[-1]}/{slot})" if slot else f"{card_name} {ecm_ip}"
    print(f"running install_cc with: \n{install_cc_cmd}")
    cmd = [
        WT_PATH,
        "new-tab",
        "--title", title,
        "wsl",
        "--",
        "bash",
        "-l",
        "-c",
        f"{install_cc_cmd} && exec bash"
    ]
    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print(f"❌ Failed to launch CC3 CLI: {e}")

def cp_fwp(cp_cmd: str, ecm_ip: str, card_ip: str, card_name: str, slot: str):
    title = f"cp_fwp {card_name} (.{ecm_ip.split('.')[-1]}/{slot})" if slot else f"{card_name} {ecm_ip}"
    cmd = [
        WT_PATH,
        "new-tab",
        "--title", title,
        "wsl",
        "--",
        "bash",
        "-l",
        "-c",
        f"{cp_cmd} && exec bash"
    ]
    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print(f"❌ Failed to copy fwp: {e}")

def launch_cc3_dte(ecm_ip: str, cc_ipv6: str, card_name: str, slot: str = ""):
    title = f"{card_name} DTE (.{ecm_ip.split('.')[-1]}/{slot})" if slot else f"{card_name} {ecm_ip}"

    # Expect script content
    expect_script = f"""#!/usr/bin/expect -f
        set timeout 10
        set ecm_ip "{ecm_ip}"
        set cc3_ip "{cc_ipv6}%mgmt"

        spawn ssh -tt -o StrictHostKeyChecking=no -p 614 root@$ecm_ip
        expect "#"
        send "ssh -tt -o StrictHostKeyChecking=no $cc3_ip\\r"
        expect "~ #"
        send "aosCoreDteConsole \\r"
        expect "localhost>"
        send "go /debug/aosFwHal/adva.hbmcard.amp\\r"
        interact
        """

    # Create temp file inside WSL filesystem
    wsl_path = "/tmp/launch_cc3_dte.expect"
    with open(wsl_path, "w") as f:
        f.write(expect_script)

    # Ensure script is executable
    subprocess.run(["chmod", "+x", wsl_path])

    # Run it in a new WSL tab via Windows Terminal
    cmd = [
        WT_PATH,
        "new-tab",
        "--title", title,
        "wsl",
        "-d", "Ubuntu",
        "--",
        "expect",
        wsl_path
    ]

    try:
        subprocess.Popen(cmd)
    except Exception as e:
        print(f"❌ Failed to launch DTE session: {e}")

def launch_and_make(amp_build_name: str):
    title = f"Building {amp_build_name}"
    print(f"telling ede to make {amp_build_name}")
    cmd = f"ede -b make {amp_build_name} && exec bash"

    full_cmd = [
        WT_PATH,
        "new-tab",
        "--title", title,
        "wsl",
        "--",
        "bash",
        "-i",
        "-c",
        cmd
    ]

    try:
        subprocess.Popen(full_cmd)
    except Exception as e:
        print(f"❌ Failed to launch WS terminal for build: {e}")

import pandas as pd
if __name__=="__main__":
    ECM_IPS = [
    "10.16.24.2", "10.16.24.3", "10.16.24.4", "10.16.24.5",
    "10.16.24.7", "10.16.24.11", "10.16.24.13", "10.16.24.80",
    "10.16.24.81",  "10.16.24.82", "10.16.24.92", "10.16.24.93", "10.16.24.94", "10.16.24.95",
    "10.16.24.96", "10.16.24.97", "10.16.24.98", "10.16.24.99"
    ]
    nodes = {}
    for ip in ECM_IPS:
        nodes[ip] = fetch_cards_from_ecm(ip=ip)

    for ecip, card_list in nodes.items():
        updated_cards = update_ecm_cards_with_ipv6(ecip=ecip, card_list=card_list)
        nodes[ecip] = updated_cards

    print(json.dumps(nodes, indent=4))
