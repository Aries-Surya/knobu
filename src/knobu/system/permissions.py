"""Checks for the access Knobu needs to read input devices."""

import grp
import os


def in_input_group() -> bool:
    """True if this session can read /dev/input (membership applies after re-login)."""
    try:
        gid = grp.getgrnam("input").gr_gid
    except KeyError:
        return False
    return os.geteuid() == 0 or gid in os.getgroups()


FIX_INPUT_GROUP = "sudo usermod -aG input $USER"


def can_write_uinput() -> bool:
    """True if Knobu can create a virtual keyboard (needed for key remapping)."""
    return os.access("/dev/uinput", os.W_OK)


# Ubuntu leaves /dev/uinput root-only; this rule (also in data/) opens it to `input`.
UINPUT_RULE = 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"'
FIX_UINPUT = (f"echo '{UINPUT_RULE}' | sudo tee /etc/udev/rules.d/70-knobu-uinput.rules"
              " && sudo udevadm control --reload && sudo udevadm trigger --name-match=uinput")
