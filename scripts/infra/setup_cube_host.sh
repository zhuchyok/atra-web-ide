#!/bin/bash
# [SINGULARITY 26.7] Setup ARM64 Linux Virtualization for CubeSandbox/Firecracker
# Optimized for Mac Studio (M2/M3 Ultra, 128GB RAM)

set -e

echo "🚀 Starting Singularity Level 7 Infrastructure Setup..."

LIMA_NAME="cube-host"

# 1. Install Lima if not present
if ! command -v limactl &> /dev/null; then
    echo "📦 Installing Lima via Homebrew..."
    /opt/homebrew/bin/brew install lima
fi

# 2. Create Lima configuration for ARM64 KVM
if ! limactl list | grep -q "$LIMA_NAME"; then
    echo "🛠️ Creating Lima configuration for ARM64 KVM..."
    limactl create --name="$LIMA_NAME" \
        --cpus=8 \
        --memory=16 \
        --disk=100 \
        --mount-type=virtiofs \
        template:ubuntu-lts
fi

# 3. Start the VM
echo "🌐 Starting ARM64 Linux VM ($LIMA_NAME)..."
limactl start --tty=false "$LIMA_NAME"

# 4. Install Firecracker inside the VM
echo "🔥 Installing Firecracker hypervisor inside VM..."
# Using the correct URL from Firecracker releases
FIRECRACKER_URL="https://github.com/firecracker-microvm/firecracker/releases/download/v1.7.0/firecracker-v1.7.0-aarch64.tgz"

limactl shell "$LIMA_NAME" sudo apt-get update
limactl shell "$LIMA_NAME" sudo apt-get install -y curl tar
limactl shell "$LIMA_NAME" curl -L "$FIRECRACKER_URL" -o /tmp/firecracker.tgz
limactl shell "$LIMA_NAME" tar -xzf /tmp/firecracker.tgz -C /tmp
# The binary is named firecracker-v1.7.0-aarch64 in the tarball
limactl shell "$LIMA_NAME" sudo mv /tmp/release-v1.7.0-aarch64/firecracker-v1.7.0-aarch64 /usr/local/bin/firecracker
limactl shell "$LIMA_NAME" sudo chmod +x /usr/local/bin/firecracker
limactl shell "$LIMA_NAME" firecracker --version

echo "✅ Infrastructure ready. CubeSandbox/Firecracker can now run natively on ARM64."
