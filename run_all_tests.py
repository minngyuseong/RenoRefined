#!/usr/bin/env python3
"""
모든 테스트 시나리오를 자동으로 실행하는 스크립트
reno와 reno_custom을 각각 테스트하고 결과를 수집
"""

import subprocess
import time
import os
import shutil
import sys

# 테스트 시나리오 정의
TEST_SCENARIOS = [
    {
        'name': '20_flows',
        'file': 'exp_multiflow_20flows.py',
        'description': '20개 TCP 연결 테스트'
    },
    {
        'name': 'high_bw_latency',
        'file': 'exp_multiflow_high_bw_latency.py',
        'description': '높은 대역폭 + 높은 지연'
    },
    {
        'name': 'high_loss',
        'file': 'exp_multiflow_high_loss.py',
        'description': '높은 패킷 손실 (1%)'
    },
    {
        'name': 'jitter',
        'file': 'exp_multiflow_jitter.py',
        'description': '지연 변동 (jitter)'
    }
]

CC_ALGOS = ['reno', 'reno_custom']
DURATION = 10  # 각 테스트 시간 (초)

def cleanup_mininet():
    """Mininet 네트워크 정리"""
    print("🧹 Cleaning up Mininet...")
    subprocess.run(['sudo', 'mn', '-c'], 
                   stdout=subprocess.DEVNULL, 
                   stderr=subprocess.DEVNULL)
    time.sleep(2)

def cleanup_old_logs():
    """이전 iperf3 로그 파일 삭제"""
    print("🗑️  Removing old iperf3 logs...")
    subprocess.run(['rm', '-f', '/tmp/iperf3_*.json'], shell=False)
    subprocess.run(['bash', '-c', 'rm -f /tmp/iperf3_*.json'])

def backup_logs(scenario_name, cc_algo):
    """로그 파일을 시나리오별로 백업"""
    backup_dir = f"/tmp/results_{scenario_name}_{cc_algo}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # /tmp/iperf3_*.json 파일을 백업 디렉토리로 복사
    import glob
    for log_file in glob.glob('/tmp/iperf3_h*_*.json'):
        shutil.copy(log_file, backup_dir)
    
    print(f"📦 Logs backed up to {backup_dir}")
    return backup_dir

def run_test(scenario, cc_algo):
    """특정 시나리오와 CC 알고리즘으로 테스트 실행"""
    print(f"\n{'='*60}")
    print(f"🚀 Running: {scenario['description']}")
    print(f"   Algorithm: {cc_algo}")
    print(f"{'='*60}")
    
    # Mininet 정리
    cleanup_mininet()
    
    # 이전 로그 삭제
    cleanup_old_logs()
    
    # 테스트 실행
    cmd = ['sudo', 'python3', scenario['file'], cc_algo]
    print(f"📝 Command: {' '.join(cmd)}")
    
    # 자동으로 exit를 입력하기 위해 echo 사용
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # duration + 여유 시간만큼 대기
    print(f"⏳ Waiting {DURATION + 5} seconds for test to complete...")
    time.sleep(DURATION + 5)
    
    # CLI에 exit 명령 전송
    try:
        process.stdin.write('exit\n')
        process.stdin.flush()
        process.wait(timeout=5)
    except:
        process.terminate()
        process.wait()
    
    print("✅ Test completed")
    
    # 로그 백업
    backup_dir = backup_logs(scenario['name'], cc_algo)
    
    return backup_dir

def main():
    print("="*60)
    print("🔬 TCP Congestion Control Test Suite")
    print("="*60)
    print(f"Scenarios: {len(TEST_SCENARIOS)}")
    print(f"Algorithms: {', '.join(CC_ALGOS)}")
    print(f"Duration per test: {DURATION}s")
    print(f"Total estimated time: ~{len(TEST_SCENARIOS) * len(CC_ALGOS) * (DURATION + 10) / 60:.0f} minutes")
    print("="*60)
    
    input("\n⏸️  Press Enter to start tests...")
    
    results_map = {}
    
    # 모든 시나리오 실행
    for scenario in TEST_SCENARIOS:
        results_map[scenario['name']] = {}
        
        for cc_algo in CC_ALGOS:
            backup_dir = run_test(scenario, cc_algo)
            results_map[scenario['name']][cc_algo] = backup_dir
    
    # 최종 정리
    cleanup_mininet()
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
    
    print("\n📊 Results saved in:")
    for scenario_name, algos in results_map.items():
        print(f"\n  {scenario_name}:")
        for cc_algo, path in algos.items():
            print(f"    - {cc_algo}: {path}")
    
    print("\n" + "="*60)
    print("🔍 Now analyzing results...")
    print("="*60)
    
    # 결과 분석 실행
    subprocess.run(['python3', 'analyze_all_results.py'])

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("❌ This script must be run with sudo!")
        print("Usage: sudo python3 run_all_tests.py")
        sys.exit(1)
    
    main()
