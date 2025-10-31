#!/bin/bash

# TCP congestion control을 cubic으로 변경
echo "Setting congestion control to cubic..."
sudo sysctl -w net.ipv4.tcp_congestion_control=cubic

# 기존 모듈 제거
echo "Removing old module..."
sudo rmmod reno_custom 2>/dev/null

# 클린 및 빌드
echo "Building module..."
make clean && make

# 빌드 성공 확인
if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

# 새 모듈 로드
echo "Loading new module..."
sudo insmod reno_custom.ko

# 모듈 로드 확인
echo "Checking module..."
lsmod | grep reno_custom

# TCP congestion control을 reno_custom으로 변경
echo "Setting congestion control to reno_custom..."
sudo sysctl -w net.ipv4.tcp_congestion_control=reno_custom

echo "Done!"
