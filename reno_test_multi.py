from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info

import time


class RenoAssignmentTopo(Topo):
    """
    과제 조건용 토폴로지

    - c1..cN  : 클라이언트 호스트들
    - srv     : 서버 호스트
    - s1      : 스위치

    클라이언트 ↔ s1 : 고속 링크 (100Mbps, 1ms)
    s1 ↔ srv       : 병목 링크 (1Mbps, 100ms)  -> RTT ≈ 200ms
    """
    def build(self, n_clients=10, bottleneck_bw=1, bottleneck_delay='100ms'):
        # 스위치 & 서버
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')
        srv = self.addHost('srv', cls=Host, defaultRoute=None)

        # 서버 링크: 1Mbps, 100ms  (과제 조건: 1Mbps, RTT 200ms 근사)
        self.addLink(srv, s1, cls=TCLink,
                     bw=bottleneck_bw, delay=bottleneck_delay)

        # 클라이언트들
        for i in range(1, n_clients + 1):
            h = self.addHost(f'c{i}', cls=Host, defaultRoute=None)
            # 클라이언트 링크는 충분히 빠르게 (100Mbps, 1ms)
            self.addLink(h, s1, cls=TCLink, bw=100, delay='1ms')


def run_experiment(n_clients=10, duration=30):
    topo = RenoAssignmentTopo(n_clients=n_clients)
    net = Mininet(topo=topo,
                  autoSetMacs=True,
                  build=True,
                  ipBase="10.0.0.0/24",
                  link=TCLink)

    net.start()
    info("*** Network started\n")

    # IP 설정 (Mininet 기본 IP 할당을 그대로 사용해도 되지만, 명시적으로 적어줘도 됨)
    srv = net.get('srv')
    srv.setIP('10.0.0.254/24')

    clients = []
    for i in range(1, n_clients + 1):
        h = net.get(f'c{i}')
        # 10.0.0.X 로 순서대로 할당
        h.setIP(f'10.0.0.{i}/24')
        clients.append(h)

    info("*** Pinging server from all clients to warm up ARP\n")
    for h in clients:
        h.cmd(f'ping -c 1 {srv.IP()} > /dev/null 2>&1')

    info("*** Starting iperf server on srv\n")
    # iperf2 기준, iperf3 쓰면 옵션만 조금 바꾸면 됨
    srv.cmd('iperf -s -p 5001 > /tmp/iperf_srv.log 2>&1 &')

    time.sleep(1)

    info("*** Starting iperf clients\n")
    for idx, h in enumerate(clients, start=1):
        log_path = f'/tmp/iperf_c{idx}.log'
        cmd = f'iperf -c {srv.IP()} -p 5001 -t {duration} -i 1 > {log_path} 2>&1 &'
        info(f"{h.name}: {cmd}\n")
        h.cmd(cmd)

    info(f"*** Waiting {duration + 5} seconds for experiment to finish\n")
    time.sleep(duration + 5)

    info("*** Collecting throughput results (last line of each iperf log)\n")
    total_mbps = 0.0
    for idx, h in enumerate(clients, start=1):
        log_path = f'/tmp/iperf_c{idx}.log'
        out = h.cmd(f'tail -n 1 {log_path}')
        info(f"{h.name} last line: {out}")

        # iperf2 결과에서 'X Mbits/sec' 부분을 파싱
        try:
            tokens = out.split()
            mbps = 0.0
            if 'Mbits/sec' in tokens:
                unit_idx = tokens.index('Mbits/sec')
                mbps = float(tokens[unit_idx - 1])
            elif 'Kbits/sec' in tokens:
                unit_idx = tokens.index('Kbits/sec')
                mbps = float(tokens[unit_idx - 1]) / 1000.0

            total_mbps += mbps
        except Exception as e:
            info(f"  [WARN] parsing error for {h.name}: {e}\n")

    info(f"\n=== SUMMARY ===\n")
    info(f"Total throughput (sum of {n_clients} flows): {total_mbps:.3f} Mbps\n")
    info(f"Link utilization against 1 Mbps bottleneck: {min(total_mbps / 1.0, 1.0) * 100:.1f}%\n")
    info("Per-flow fairness analysis can be done from /tmp/iperf_c*.log\n")

    # 필요하면 CLI 열어서 dmesg 등 바로 확인 가능
    CLI(net)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run_experiment(n_clients=10, duration=30)

