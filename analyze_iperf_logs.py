import json
import glob
import os
import math

LINK_CAPACITY_GBPS = 1.0   # 링크 용량 (Gbps) - 1000 Mbps

def extract_bps(json_data):
    """
    iperf3 JSON 구조가 어떤 형식이든 최대한 sender throughput(bps)을 추출한다.
    실패하면 0 반환.
    """

    # 0) 에러 메시지 포함된 경우
    if "error" in json_data:
        print("  [!] iperf3 error:", json_data["error"])
        return 0

    # 1) end.sum_sent.bits_per_second
    try:
        return json_data["end"]["sum_sent"]["bits_per_second"]
    except:
        pass

    # 2) end.sum.bits_per_second (일부 버전은 sum_sent 대신 sum만 존재)
    try:
        return json_data["end"]["sum"]["bits_per_second"]
    except:
        pass

    # 3) end.sum_received.bits_per_second (중간에서 sum_received만 존재)
    try:
        return json_data["end"]["sum_received"]["bits_per_second"]
    except:
        pass

    # 4) end.streams[0].sender.bits_per_second
    try:
        return json_data["end"]["streams"][0]["sender"]["bits_per_second"]
    except:
        pass

    # 5) end.streams[0].bits_per_second (sender 필드가 없을 때)
    try:
        return json_data["end"]["streams"][0]["bits_per_second"]
    except:
        pass

    # 6) 어떤 것도 없으면 0
    return 0

def parse_iperf_json(path):
    """파일을 읽고 sender throughput(Gbps) 반환"""
    with open(path, "r") as f:
        data = json.load(f)

    bps = extract_bps(data)
    return bps / 1e9


def jain_fairness(values):
    if not values:
        return 0.0
    s = sum(values)
    s2 = sum(v * v for v in values)
    n = len(values)
    return (s * s) / (n * s2) if s2 > 0 else 0.0


def analyze_algo(algo):
    pattern = f"/tmp/iperf3_h*_{algo}.json"
    files = sorted(glob.glob(pattern))

    print(f"\n==============================")
    print(f"  TCP CC = {algo}")
    print(f"  Files: {len(files)}개")
    print(f"==============================")

    if len(files) == 0:
        print("로그가 없습니다:", pattern)
        return

    throughputs = []
    hosts = []

    for path in files:
        base = os.path.basename(path)
        host = base.split("_")[0].replace("iperf3_", "")  # h2 등
        gbps = parse_iperf_json(path)

        throughputs.append(gbps)
        hosts.append(host)

    print("\n[각 흐름별 Throughput]")
    print("Host\tThroughput (Gbps)")
    print("--------------------------------")
    for h, g in zip(hosts, throughputs):
        print(f"{h}\t{g:.3f}")

    total = sum(throughputs)
    util = (total / LINK_CAPACITY_GBPS) * 100.0
    fairness = jain_fairness(throughputs)

    print("\n[요약]")
    print(f"총 흐름 수 (N)\t: {len(throughputs)}")
    print(f"총 Throughput\t: {total:.3f} Gbps")
    print(f"Link Utilization\t: {util:.1f} %")
    print(f"Jain Fairness Index\t: {fairness:.3f}")
    print("================================\n")


if __name__ == "__main__":
    for algo in ["reno", "reno_custom"]:
        analyze_algo(algo)

