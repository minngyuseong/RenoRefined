#!/usr/bin/env python3
"""
TCP Congestion Control 성능 비교 보고서 생성
결과를 마크다운 형식으로 저장
"""

import json
import glob
import os
import statistics
from datetime import datetime

# 테스트 시나리오별 링크 용량 정의
SCENARIO_CONFIGS = {
    '20_flows': {
        'description': '20개 TCP 연결',
        'link_capacity_gbps': 1.0,
        'num_flows': 20,
        'params': 'BW: 1Gbps, Delay: 10ms, Loss: 0.1%'
    },
    'high_bw_latency': {
        'description': '높은 대역폭 + 높은 지연',
        'link_capacity_gbps': 10.0,
        'num_flows': 5,
        'params': 'BW: 10Gbps, Delay: 50ms, Loss: 0.1%'
    },
    'high_loss': {
        'description': '높은 패킷 손실',
        'link_capacity_gbps': 1.0,
        'num_flows': 5,
        'params': 'BW: 1Gbps, Delay: 10ms, Loss: 1.0%'
    },
    'jitter': {
        'description': '지연 변동 (jitter)',
        'link_capacity_gbps': 1.0,
        'num_flows': 5,
        'params': 'BW: 1Gbps, Delay: 50ms, Jitter: 10ms, Loss: 0.1%'
    }
}

CC_ALGOS = ['reno', 'reno_custom']

def extract_metrics_from_json(json_data):
    """iperf3 JSON에서 메트릭 추출"""
    metrics = {
        'throughput_bps': 0,
        'mean_rtt_ms': 0,
        'retransmits': 0
    }
    
    if "error" in json_data:
        return metrics
    
    try:
        metrics['throughput_bps'] = json_data["end"]["sum_sent"]["bits_per_second"]
    except:
        try:
            metrics['throughput_bps'] = json_data["end"]["sum"]["bits_per_second"]
        except:
            pass
    
    try:
        metrics['mean_rtt_ms'] = json_data["end"]["streams"][0]["sender"]["mean_rtt"] / 1000.0
    except:
        pass
    
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
                throughputs.append(metrics['throughput_bps'] / 1e9)
            
            if metrics['mean_rtt_ms'] > 0:
                latencies.append(metrics['mean_rtt_ms'])
            
            retransmits_total += metrics['retransmits']
            
        except Exception as e:
            continue
    
    if len(throughputs) == 0:
        return None
    
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

def generate_report():
    """마크다운 형식의 보고서 생성"""
    
    report = []
    report.append("# TCP Congestion Control 성능 비교 보고서\n")
    report.append(f"**작성일**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n")
    report.append("---\n\n")
    
    # 1. 요약
    report.append("## 1. 실험 개요\n\n")
    report.append("### 1.1 목적\n")
    report.append("TCP Reno와 개선된 Reno Custom 알고리즘의 성능을 다양한 네트워크 환경에서 비교 분석\n\n")
    
    report.append("### 1.2 테스트 시나리오\n\n")
    report.append("| 시나리오 | 설명 | 네트워크 파라미터 |\n")
    report.append("|---------|------|------------------|\n")
    for idx, (scenario_name, config) in enumerate(SCENARIO_CONFIGS.items(), 1):
        report.append(f"| {idx}. {config['description']} | {config['num_flows']}개 TCP 연결 | {config['params']} |\n")
    report.append("\n")
    
    report.append("### 1.3 평가 지표\n\n")
    report.append("- **Link Utilization (%)**: 링크 용량 대비 사용률\n")
    report.append("- **Average Latency (ms)**: 평균 왕복 지연 시간\n")
    report.append("- **Fairness Index**: Jain's Fairness Index (1에 가까울수록 공정)\n")
    report.append("- **Total Retransmits**: 총 재전송 횟수 (낮을수록 우수)\n\n")
    
    report.append("---\n\n")
    
    # 2. 상세 결과
    report.append("## 2. 실험 결과\n\n")
    
    all_results = {}
    
    for scenario_name, config in SCENARIO_CONFIGS.items():
        report.append(f"### 2.{list(SCENARIO_CONFIGS.keys()).index(scenario_name) + 1} {config['description']}\n\n")
        report.append(f"**네트워크 환경**: {config['params']}  \n")
        report.append(f"**TCP 연결 수**: {config['num_flows']}개  \n")
        report.append(f"**링크 용량**: {config['link_capacity_gbps']} Gbps\n\n")
        
        results = {}
        for cc_algo in CC_ALGOS:
            results[cc_algo] = analyze_scenario(scenario_name, cc_algo)
        
        all_results[scenario_name] = results
        
        if results['reno'] and results['reno_custom']:
            report.append("#### 성능 비교 표\n\n")
            report.append("| 지표 | TCP Reno | TCP Reno Custom | 개선율 |\n")
            report.append("|------|----------|-----------------|-------|\n")
            
            reno = results['reno']
            custom = results['reno_custom']
            
            # Link Utilization
            improvement = ((custom['link_utilization_percent'] - reno['link_utilization_percent']) / reno['link_utilization_percent'] * 100) if reno['link_utilization_percent'] > 0 else 0
            report.append(f"| Link Utilization (%) | {reno['link_utilization_percent']:.2f} | {custom['link_utilization_percent']:.2f} | {improvement:+.1f}% |\n")
            
            # Throughput
            improvement = ((custom['total_throughput_gbps'] - reno['total_throughput_gbps']) / reno['total_throughput_gbps'] * 100) if reno['total_throughput_gbps'] > 0 else 0
            report.append(f"| Total Throughput (Gbps) | {reno['total_throughput_gbps']:.3f} | {custom['total_throughput_gbps']:.3f} | {improvement:+.1f}% |\n")
            
            # Latency (낮을수록 좋음)
            if reno['avg_latency_ms'] > 0 and custom['avg_latency_ms'] > 0:
                improvement = ((reno['avg_latency_ms'] - custom['avg_latency_ms']) / reno['avg_latency_ms'] * 100)
                report.append(f"| Average Latency (ms) | {reno['avg_latency_ms']:.2f} | {custom['avg_latency_ms']:.2f} | {improvement:+.1f}% |\n")
            
            # Fairness
            improvement = ((custom['fairness_index'] - reno['fairness_index']) / reno['fairness_index'] * 100) if reno['fairness_index'] > 0 else 0
            report.append(f"| Fairness Index | {reno['fairness_index']:.3f} | {custom['fairness_index']:.3f} | {improvement:+.1f}% |\n")
            
            # Retransmits (낮을수록 좋음)
            improvement = ((reno['retransmits'] - custom['retransmits']) / reno['retransmits'] * 100) if reno['retransmits'] > 0 else 0
            report.append(f"| Total Retransmits | {reno['retransmits']} | {custom['retransmits']} | {improvement:+.1f}% |\n")
            
            report.append("\n")
            
            # 승자 판정
            report.append("#### 종합 평가\n\n")
            
            wins = {'reno': 0, 'reno_custom': 0}
            
            if custom['link_utilization_percent'] > reno['link_utilization_percent']:
                wins['reno_custom'] += 1
                report.append("- ✅ **Link Utilization**: Reno Custom 우수\n")
            else:
                wins['reno'] += 1
                report.append("- ✅ **Link Utilization**: Reno 우수\n")
            
            if custom['avg_latency_ms'] > 0 and reno['avg_latency_ms'] > 0:
                if custom['avg_latency_ms'] < reno['avg_latency_ms']:
                    wins['reno_custom'] += 1
                    report.append("- ✅ **Latency**: Reno Custom 우수 (낮은 지연)\n")
                else:
                    wins['reno'] += 1
                    report.append("- ✅ **Latency**: Reno 우수 (낮은 지연)\n")
            
            if custom['fairness_index'] > reno['fairness_index']:
                wins['reno_custom'] += 1
                report.append("- ✅ **Fairness**: Reno Custom 우수\n")
            else:
                wins['reno'] += 1
                report.append("- ✅ **Fairness**: Reno 우수\n")
            
            if custom['retransmits'] < reno['retransmits']:
                wins['reno_custom'] += 1
                report.append("- ✅ **Retransmits**: Reno Custom 우수 (적은 재전송)\n")
            else:
                wins['reno'] += 1
                report.append("- ✅ **Retransmits**: Reno 우수 (적은 재전송)\n")
            
            if wins['reno_custom'] > wins['reno']:
                report.append(f"\n**🏆 이 시나리오의 Winner: TCP Reno Custom** ({wins['reno_custom']}/{wins['reno'] + wins['reno_custom']} 지표에서 우수)\n\n")
            elif wins['reno'] > wins['reno_custom']:
                report.append(f"\n**🏆 이 시나리오의 Winner: TCP Reno** ({wins['reno']}/{wins['reno'] + wins['reno_custom']} 지표에서 우수)\n\n")
            else:
                report.append("\n**🤝 무승부**\n\n")
        else:
            report.append("⚠️ 유효한 결과 없음\n\n")
        
        report.append("---\n\n")
    
    # 3. 종합 분석
    report.append("## 3. 종합 분석\n\n")
    
    report.append("### 3.1 시나리오별 요약\n\n")
    report.append("| 시나리오 | Reno Utilization | Custom Utilization | Reno Latency | Custom Latency | Reno Fairness | Custom Fairness |\n")
    report.append("|---------|------------------|--------------------|--------------|-----------------|--------------|-----------------|\n")
    
    for scenario_name, config in SCENARIO_CONFIGS.items():
        if scenario_name in all_results:
            reno = all_results[scenario_name].get('reno')
            custom = all_results[scenario_name].get('reno_custom')
            if reno and custom:
                report.append(f"| {config['description']} | {reno['link_utilization_percent']:.2f}% | {custom['link_utilization_percent']:.2f}% | {reno['avg_latency_ms']:.2f}ms | {custom['avg_latency_ms']:.2f}ms | {reno['fairness_index']:.3f} | {custom['fairness_index']:.3f} |\n")
    
    report.append("\n")
    
    # 4. 결론
    report.append("## 4. 결론\n\n")
    report.append("### 4.1 주요 발견사항\n\n")
    
    # 시나리오별 승자 카운트
    overall_wins = {'reno': 0, 'reno_custom': 0}
    
    for scenario_name, results in all_results.items():
        reno = results.get('reno')
        custom = results.get('reno_custom')
        
        if reno and custom:
            scenario_wins = 0
            # 4개 지표 비교
            if custom['link_utilization_percent'] > reno['link_utilization_percent']:
                scenario_wins += 1
            if custom['avg_latency_ms'] > 0 and reno['avg_latency_ms'] > 0 and custom['avg_latency_ms'] < reno['avg_latency_ms']:
                scenario_wins += 1
            if custom['fairness_index'] > reno['fairness_index']:
                scenario_wins += 1
            if custom['retransmits'] < reno['retransmits']:
                scenario_wins += 1
            
            if scenario_wins > 2:
                overall_wins['reno_custom'] += 1
            elif scenario_wins < 2:
                overall_wins['reno'] += 1
    
    report.append(f"- 총 {len(SCENARIO_CONFIGS)}개 시나리오 중:\n")
    report.append(f"  - **TCP Reno** 우세: {overall_wins['reno']}개 시나리오\n")
    report.append(f"  - **TCP Reno Custom** 우세: {overall_wins['reno_custom']}개 시나리오\n\n")
    
    report.append("### 4.2 Reno Custom의 특징\n\n")
    report.append("TCP Reno Custom은 다음과 같은 특징을 보임:\n\n")
    report.append("1. **대역폭 추정 (BWE)**: 패킷 ACK 정보를 활용한 실시간 대역폭 추정\n")
    report.append("2. **BDP 기반 ssthresh**: 손실 발생 시 BDP를 고려한 적응적 임계값 설정\n")
    report.append("3. **혼잡 윈도우 제한**: cwnd가 BDP의 2배를 넘지 않도록 제한하여 버퍼 팽창 방지\n\n")
    
    report.append("### 4.3 권장사항\n\n")
    
    if overall_wins['reno_custom'] > overall_wins['reno']:
        report.append("**TCP Reno Custom이 대부분의 시나리오에서 우수한 성능을 보임**\n\n")
        report.append("- 특히 높은 대역폭-지연 곱(BDP) 환경에서 효과적\n")
        report.append("- 공정성과 재전송 감소 측면에서 개선됨\n")
    else:
        report.append("**TCP Reno가 여전히 안정적인 성능을 보임**\n\n")
        report.append("- 특정 환경에서는 표준 Reno가 더 효율적일 수 있음\n")
        report.append("- Reno Custom의 추가 최적화가 필요할 수 있음\n")
    
    report.append("\n---\n\n")
    report.append("*본 보고서는 자동 생성되었습니다.*\n")
    
    return ''.join(report)

def main():
    report_content = generate_report()
    
    # 파일로 저장
    output_file = "TCP_Performance_Report.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"✅ 보고서가 생성되었습니다: {output_file}")
    print("\n" + "="*60)
    print(report_content)
    print("="*60)

if __name__ == "__main__":
    main()
