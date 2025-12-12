#!/usr/bin/env python3
"""
모든 테스트 결과를 분석하고 요약하는 스크립트
Link Utilization, Latency, Fairness를 계산
"""

import json
import glob
import os
import statistics

# 테스트 시나리오별 링크 용량 정의
SCENARIO_CONFIGS = {
    '20_flows': {
        'description': '20개 TCP 연결',
        'link_capacity_gbps': 1.0,
        'num_flows': 20
    },
    'high_bw_latency': {
        'description': '높은 대역폭 + 높은 지연',
        'link_capacity_gbps': 10.0,
        'num_flows': 5
    },
    'high_loss': {
        'description': '높은 패킷 손실',
        'link_capacity_gbps': 1.0,
        'num_flows': 5
    },
    'jitter': {
        'description': '지연 변동 (jitter)',
        'link_capacity_gbps': 1.0,
        'num_flows': 5
    }
}

CC_ALGOS = ['reno', 'reno_custom']

def extract_metrics_from_json(json_data):
    """
    iperf3 JSON에서 throughput, latency 등 메트릭 추출
    """
    metrics = {
        'throughput_bps': 0,
        'mean_rtt_ms': 0,
        'retransmits': 0
    }
    
    # 에러 체크
    if "error" in json_data:
        return metrics
    
    # Throughput 추출
    try:
        metrics['throughput_bps'] = json_data["end"]["sum_sent"]["bits_per_second"]
    except:
        try:
            metrics['throughput_bps'] = json_data["end"]["sum"]["bits_per_second"]
        except:
            pass
    
    # Mean RTT 추출
    try:
        metrics['mean_rtt_ms'] = json_data["end"]["streams"][0]["sender"]["mean_rtt"] / 1000.0
    except:
        pass
    
    # Retransmits 추출
    try:
        metrics['retransmits'] = json_data["end"]["streams"][0]["sender"]["retransmits"]
    except:
        pass
    
    return metrics

def jain_fairness(values):
    """Jain's Fairness Index 계산"""
    if not values or len(values) == 0:
        return 0.0
    s = sum(values)
    s2 = sum(v * v for v in values)
    n = len(values)
    return (s * s) / (n * s2) if s2 > 0 else 0.0

def analyze_scenario(scenario_name, cc_algo):
    """특정 시나리오의 결과 분석"""
    result_dir = f"/tmp/results_{scenario_name}_{cc_algo}"
    
    if not os.path.exists(result_dir):
        return None
    
    config = SCENARIO_CONFIGS[scenario_name]
    json_files = glob.glob(f"{result_dir}/iperf3_h*_{cc_algo}.json")
    
    if len(json_files) == 0:
        return None
    
    throughputs = []
    latencies = []
    retransmits_total = 0
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            metrics = extract_metrics_from_json(data)
            
            if metrics['throughput_bps'] > 0:
                throughputs.append(metrics['throughput_bps'] / 1e9)  # Gbps로 변환
            
            if metrics['mean_rtt_ms'] > 0:
                latencies.append(metrics['mean_rtt_ms'])
            
            retransmits_total += metrics['retransmits']
            
        except Exception as e:
            continue
    
    if len(throughputs) == 0:
        return None
    
    # 메트릭 계산
    total_throughput = sum(throughputs)
    link_utilization = (total_throughput / config['link_capacity_gbps']) * 100.0
    fairness = jain_fairness(throughputs)
    avg_latency = statistics.mean(latencies) if latencies else 0
    
    return {
        'total_throughput_gbps': total_throughput,
        'link_utilization_percent': link_utilization,
        'fairness_index': fairness,
        'avg_latency_ms': avg_latency,
        'retransmits': retransmits_total,
        'num_flows': len(throughputs)
    }

def print_comparison_table():
    """모든 결과를 비교 테이블로 출력"""
    
    print("\n" + "="*100)
    print("📊 TCP Congestion Control Performance Comparison")
    print("="*100)
    
    for scenario_name, config in SCENARIO_CONFIGS.items():
        print(f"\n{'='*100}")
        print(f"🔬 Scenario: {config['description']}")
        print(f"{'='*100}")
        
        results = {}
        for cc_algo in CC_ALGOS:
            results[cc_algo] = analyze_scenario(scenario_name, cc_algo)
        
        # 헤더 출력
        print(f"\n{'Metric':<30} {'Reno':<25} {'Reno Custom':<25} {'Winner':<15}")
        print("-" * 100)
        
        # Link Utilization
        if results['reno'] and results['reno_custom']:
            reno_util = results['reno']['link_utilization_percent']
            custom_util = results['reno_custom']['link_utilization_percent']
            winner = '🏆 Reno' if reno_util > custom_util else '🏆 Reno Custom' if custom_util > reno_util else '🤝 Tie'
            print(f"{'Link Utilization (%)':<30} {reno_util:<24.2f} {custom_util:<24.2f} {winner:<15}")
            
            # Throughput
            reno_tput = results['reno']['total_throughput_gbps']
            custom_tput = results['reno_custom']['total_throughput_gbps']
            winner = '🏆 Reno' if reno_tput > custom_tput else '🏆 Reno Custom' if custom_tput > reno_tput else '🤝 Tie'
            print(f"{'Total Throughput (Gbps)':<30} {reno_tput:<24.3f} {custom_tput:<24.3f} {winner:<15}")
            
            # Latency (lower is better)
            reno_lat = results['reno']['avg_latency_ms']
            custom_lat = results['reno_custom']['avg_latency_ms']
            if reno_lat > 0 and custom_lat > 0:
                winner = '🏆 Reno' if reno_lat < custom_lat else '🏆 Reno Custom' if custom_lat < reno_lat else '🤝 Tie'
                print(f"{'Average Latency (ms)':<30} {reno_lat:<24.2f} {custom_lat:<24.2f} {winner:<15}")
            
            # Fairness
            reno_fair = results['reno']['fairness_index']
            custom_fair = results['reno_custom']['fairness_index']
            winner = '🏆 Reno' if reno_fair > custom_fair else '🏆 Reno Custom' if custom_fair > reno_fair else '🤝 Tie'
            print(f"{'Fairness Index':<30} {reno_fair:<24.3f} {custom_fair:<24.3f} {winner:<15}")
            
            # Retransmits (lower is better)
            reno_retx = results['reno']['retransmits']
            custom_retx = results['reno_custom']['retransmits']
            winner = '🏆 Reno' if reno_retx < custom_retx else '🏆 Reno Custom' if custom_retx < reno_retx else '🤝 Tie'
            print(f"{'Total Retransmits':<30} {reno_retx:<24} {custom_retx:<24} {winner:<15}")
        else:
            print("⚠️  No valid results found for this scenario")
    
    print("\n" + "="*100)
    print("✅ Analysis Complete!")
    print("="*100)

def main():
    print_comparison_table()

if __name__ == "__main__":
    main()
