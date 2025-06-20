import streamlit as st
import os
import json
import pandas as pd
from dataclasses import dataclass

from shelfRay import launch_and_make, launch_ecm_terminal, launch_cc3_cli, launch_cc3_dte, deploy, cp_fwp, serial
from parser import AMPLIFIER_REGISTRY

ECM_IPS = [
    "10.16.24.2", "10.16.24.3", "10.16.24.4", "10.16.24.5",
    "10.16.24.7", "10.16.24.11", "10.16.24.13", "10.16.24.80",
    "10.16.24.81",  "10.16.24.82", "10.16.24.84", "10.16.24.85",
    "10.16.24.92", "10.16.24.93", "10.16.24.94", "10.16.24.95",
    "10.16.24.96", "10.16.24.97", "10.16.24.98", "10.16.24.99"
]

CACHE_FILE = os.path.expanduser("~/jterm/nodes_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

@st.cache_data(show_spinner=False)
def get_cached_nodes():
    return load_cache()

# Streamlit App
icon_path = os.path.expanduser("~/jterm/icon_one_removebg.png")
st.set_page_config(page_title="SRay", layout="wide", page_icon=icon_path)
col1, col2 = st.columns([0.25, 3])
with col1:
    st.image(icon_path, width=150)
with col2:
    st.title("JTerm")

nodes = get_cached_nodes()

amplifiers_by_type = {}
for ecm_ip, cards in nodes.items():
    for card in cards:
        amp_type = card.get("name")
        if amp_type:
            amplifiers_by_type.setdefault(amp_type, []).append((ecm_ip, card))

col1, col2 = st.columns([6, 4])
with col1:
    with st.expander(f"📋 Clipboard"):
        st.code("tail -f /var/opt/adva/aos/log/tracelog/aosFwHal.log")
        st.code("tail -n 2000 /var/opt/adva/aos/log/tracelog/aosFwHal.log")
        st.code("tail -n 2000 /var/opt/adva/aos/log/tracelog/aosFwHal.log | awk 'match($0, /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z\|core\.sirm\s+\|NOTICE\|THD:[0-9A-Fa-f]+\| =+ Starting AOS run [0-9]+ =+$/) {last=NR} {lines[NR]=$0} END {for (i=last; i<=NR; i++) print lines[i]}'")
        st.code("find / -type f -name '*Config.json' 2>/dev/null")
        st.code("go /debug/aosFwHal/trace-log && enable-in-memory-buffer off && clear")

@dataclass
class Package:
    name: str
    path: str
    def __repr__(self):
        return f"{self.name}"

if 'selected_packages' not in st.session_state:
    st.session_state['selected_packages'] = []
package_options = []
with open(os.path.expanduser("~/jterm/packages_cache.json"), "r") as f:
    package_cache = json.load(f)

def split_package_names(packages: list[dict[str]]) -> list[tuple[str]]:
    return [(pkg['path'], pkg['path'].split('/')[-1].replace('.so', '')) for pkg in packages]

package_options = [Package(name=pkg_name, path=pkg_path) for (pkg_path, pkg_name) in split_package_names(package_cache.get("packages", []))]
with col2:
    st.multiselect("Select local package under development", options=package_options, key='selected_packages')

for amp_type in AMPLIFIER_REGISTRY.keys():
    amp_list = amplifiers_by_type.get(amp_type, [])
    with st.expander(f"🔧 {amp_type} ({len(amp_list)} units)"):
        for idx, (ecm_ip, card) in enumerate(sorted(amp_list, key=lambda x: (x[0], x[1].get("slot", "")))):
            short_ip = ecm_ip.split('.')[-1]
            ipv6 = card.get("ipv6")
            card_name = card.get("name")
            slot = card.get("slot")
            col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, _ = st.columns([2, 1, 1, 1, 1, 1.1, 2, 1, 1, 1, 2])
            with col1:
                st.write(f"ECM: `.{short_ip}` | Slot: `{card['slot']}` | Status: `{card['status']}`")
                # jenkins_link = f"https://atl-jenkins-sitsys.rd.advaoptical.com/view/F8%20Amp%20Regression1/job/Stingrays/job/Regression/job/{amp_type}/"
                # image_path = "jenkins.png"
                # with open(image_path, "rb") as img_file:
                #     img_bytes = img_file.read()
                #     img_base64 = base64.b64encode(img_bytes).decode()
                # st.markdown(
                #     f"""
                #     <a href="{jenkins_link}" target="_blank" style="text-decoration: none;">
                #         <img src="data:image/png;base64,{img_base64}" alt="Jenkins" style="width:24px; height:24px; cursor:pointer;" />
                #     </a>
                #     """,
                #     unsafe_allow_html=True
                # )
            with col2:
                if st.button(f".{short_ip} CLI", key=f"ecm_cli_{ecm_ip}_{slot}_{idx}"):
                    launch_ecm_terminal(ecm_ip, port=22)
            with col3:
                if st.button(f".{short_ip} Node", key=f"ecm_linux_{ecm_ip}_{slot}_{idx}"):
                    launch_ecm_terminal(ecm_ip, port=614)
            if ipv6 and card_name in AMPLIFIER_REGISTRY:
                with col4:
                    if st.button(f".{short_ip}/{slot} Card", key=f"cc_linux_{ipv6}_{idx}"):
                        launch_cc3_cli(ecm_ip, ipv6, card_name, slot)
                with col5:
                    if st.button(f".{short_ip}/{slot} Card DTE", key=f"cc_dte_{ipv6}_{idx}"):
                        launch_cc3_dte(ecm_ip=ecm_ip, cc_ipv6=ipv6, card_name=card_name, slot=slot)
                build_name, tar_name, fwp_name = AMPLIFIER_REGISTRY[card_name]
                with col6:
                    if st.button(f"make {build_name}", key=f"make_{build_name}_{idx}"):
                        launch_and_make(amp_build_name=build_name)
                with col7:
                    LOCAL_CARD_LIB_BASE_PATH = lambda card_build_name: f"/mnt/workspace/build/arm7-32bit/Build/{card_build_name}/staging/base/"
                    REMOTE_CARD_LIB_BASE_PATH = "/"
                    pkg_paths = [f"{LOCAL_CARD_LIB_BASE_PATH(build_name)}{pkg.path}" for pkg in st.session_state.get('selected_packages', [])]
                    
                    LOCAL_CARD_CONFIG_PATH = lambda card_build_name: f"/mnt/workspace/build/arm7-32bit/Build/{card_build_name}/HbmConfigAmp.json"
                    cfg_path = f"{LOCAL_CARD_CONFIG_PATH(build_name)}"
                    
                    for path in pkg_paths:
                        deploy_cmd = f"cd /mnt/workspace && ./devploy -r {ecm_ip} {ipv6} {cfg_path} {path}"
                    pkg_names = [f"{pkg.name}" for pkg in st.session_state.get('selected_packages', [])]
                    if st.button(f"deploy {','.join(pkg_names)}", key=f"deploy_{build_name}_{idx}"):
                        deploy(deploy_cmd=deploy_cmd)
                    # st.write(f"{pkg_paths}")
                    # cc_path = "/mnt/workspace/build/arm7-32bit/Build/cc3/staging/f8-cc3-base-*.tar.bz2"
                    # amp_path = f"/mnt/workspace/build/arm7-32bit/Build/{build_name}/staging/{tar_name}-base-*.tar.bz2"
                    # install_cmd = f" cd /mnt/workspace && ./install_cc {ecm_ip} {ipv6} {cc_path} {amp_path}"
                    # if st.button(f"install_cc", key=f"install_cc_{build_name}_{idx}"):
                    #     install_cc(install_cc_cmd=install_cmd, ecm_ip=ecm_ip, card_name=card_name, slot=slot)
                with col8:
                    if st.button(f"copy fwp", key=f"install_fwp_{build_name}_{idx}"):
                        fwp_path = f"/mnt/workspace/build/arm7-32bit/Build/{build_name}/{fwp_name}.fwp"
                        cp_cmd = f"cd /mnt/workspace/repo && ./cp_fwp {ecm_ip} {ipv6} {fwp_path} /opt/adva/aos/lib/firmware"
                        cp_fwp(cp_cmd=cp_cmd, ecm_ip=ecm_ip, card_ip=ipv6, card_name=card_name, slot=slot)
                with col9:
                    term_server = card.get("term_server")
                    term_port = card.get("term_port")
                    if term_server and term_port:
                        if st.button("serial", key=f"serial_{build_name}_{idx}"):
                            serial(term_server=term_server, term_port=term_port, card_name=card_name, ecm_ip=ecm_ip, slot=slot)
                with col10:
                    st.checkbox(label="active", key=f"active_{amp_type}_{ecm_ip}_{idx}")
            else:
                with col4:
                    st.warning("🚫 IPv6")


rows = []
for ecm_ip, cards in nodes.items():
    for card in cards:
        row = {
            "ecm_ip": ecm_ip,
            "type": card.get("name"),
            "slot": card.get("slot"),
            "part_number": card.get("part_number"),
            "status": card.get("status"),
            "ipv6": card.get("ipv6", None),
            "description": card.get("description")
        }
        rows.append(row)

df = pd.DataFrame(rows)
st.dataframe(df)
