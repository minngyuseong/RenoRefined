from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time

class MultiFlowTopo(Topo):
    def build(self):
        # 서버 1개, 클라이언트 5개
        server = self.addHost('h1', cls=Host)
        clients = [self.addHost(f'h{i}', cls=Host) for i in range(2, 7)]
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch)

        # 높은 bandwidth + 높은 latency 테스트
        link_opts = dict(
            cls=TCLink,
            bw=10000,       # 10 Gbit/s - 높은 대역폭 ⭐
            delay='50ms',   # 100ms RTT - 높은 지연 ⭐
            loss=0.1        # 0.1% 패킷 손실 (기본)
            # jitter 없음 (기본)
        )

        self.addLink(server, s1, **link_opts)
        for h in clients:
            self.addLink(h, s1, **link_opts)

def runExperiment(cc_algo='reno', duration=30):
    topo = MultiFlowTopo()
    net = Mininet(topo=topo, autoSetMacs=True, build=True)
    net.start()

    server = net.get('h1')
    clients = [net.get(f'h{i}') for i in range(2, 7)]

    info(f"*** Set TCP CC to {cc_algo}\n")
    for h in net.hosts:
        h.cmd(f"sysctl -w net.ipv4.tcp_congestion_control={cc_algo} > /dev/null")

    server_ip = server.IP()

    info("*** Kill old iperf3 servers (if any)\n")
    server.cmd("pkill iperf3")

    # 5개의 서버 실행: 5201 ~ 5205
    info("*** Start 5 iperf3 servers on h1 (ports 5201~5205)\n")
    for i in range(5):
        port = 5201 + i
        server.cmd(f"iperf3 -s -p {port} > /tmp/iperf3_s_{port}.log 2>&1 &")

    time.sleep(1)

    # 5개의 클라이언트를 각기 다른 포트로 연결
    info("*** Start 5 concurrent iperf3 clients (h2~h6)\n")
    for i, c in enumerate(clients):
        port = 5201 + i
        host_num = i + 2
        logFile = f"/tmp/iperf3_h{host_num}_{cc_algo}.json"
        cmd = f"iperf3 -J -c {server_ip} -p {port} -t {duration} > {logFile} &"
        info(f"h{host_num}: iperf3 -c {server_ip}:{port}\n")
        c.cmd(cmd)
        time.sleep(0.2)

    info(f"*** Running {duration} seconds...\n")
    time.sleep(duration + 3)

    info("*** iperf3 finished. You can now run the analyzer script.\n")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel('info')
    import sys
    
    cc_algo = sys.argv[1] if len(sys.argv) > 1 else 'reno'
    runExperiment(cc_algo, duration=10)
