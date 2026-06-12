#!/usr/bin/env bash
set -u

echo "== system =="
uname -a
if [ -r /etc/os-release ]; then
  sed -n '1,8p' /etc/os-release
fi
ldd --version | sed -n '1p' || true

echo
echo "== virtualization =="
systemd-detect-virt || true
lscpu | sed -n '/Architecture:/p;/CPU(s):/p;/Vendor ID:/p;/BIOS Vendor ID:/p;/Hypervisor vendor:/p;/Virtualization type:/p'
if grep -Eq '(^flags|^Features).* (vmx|svm)( |$)' /proc/cpuinfo; then
  echo "cpu_virtualization_flag: present"
else
  echo "cpu_virtualization_flag: missing"
fi

echo
echo "== devices =="
ls -l /dev/kvm /dev/net/tun 2>&1 || true

echo
echo "== kernel config =="
if [ -r "/lib/modules/$(uname -r)/config" ]; then
  grep -E 'CONFIG_KVM|CONFIG_KVM_INTEL|CONFIG_KVM_AMD|CONFIG_USERFAULTFD|CONFIG_VHOST_NET' "/lib/modules/$(uname -r)/config" || true
else
  echo "kernel config not readable"
fi

echo
echo "== commands =="
for cmd in curl tar ip iptables forkd forkd-controller firecracker docker ctr kubectl; do
  command -v "$cmd" || true
done

echo
echo "== forkd =="
if command -v forkd >/dev/null 2>&1; then
  forkd --version || true
  forkd doctor || true
else
  echo "forkd: not installed"
fi
