from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time

class MultiFlowTopo(Topo):
    def build(self, num_clients=20):
        # 서버 1개, 클라이언트 20개
        server = self.addHost('h1', cls=Host)
        clients = [self.addHost(f'h{i}', cls=Host) for i in range(2, num_clients + 2)]
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch)

        # 20개 TCP 연결 테스트 (나머지는 기본 설정)
        link_opts = dict(
            cls=TCLink,
            bw=1000,        # 1 Gbit/s (기본)
            delay='10ms',   # 20ms RTT (기본)
            loss=0.1        # 0.1% 패킷 손실 (기본)
        )

        self.addLink(server, s1, **link_opts)
        for h in clients:
            self.addLink(h, s1, **link_opts)

def runExperiment(cc_algo='reno', duration=30, num_clients=20):
    topo = MultiFlowTopo(num_clients=num_clients)
    net = Mininet(topo=topo, autoSetMacs=True, build=True)
    net.start()

    server = net.get('h1')
    clients = [net.get(f'h{i}') for i in range(2, num_clients + 2)]

    info(f"*** Set TCP CC to {cc_algo}\n")
    for h in net.hosts:
        h.cmd(f"sysctl -w net.ipv4.tcp_congestion_control={cc_algo} > /dev/null")

    server_ip = server.IP()

    info("*** Kill old iperf3 servers (if any)\n")
    server.cmd("pkill iperf3")

    # num_clients개의 서버 실행: 5201 ~ 5201+num_clients-1
    info(f"*** Start {num_clients} iperf3 servers on h1 (ports 5201~{5200+num_clients})\n")
    for i in range(num_clients):
        port = 5201 + i
        server.cmd(f"iperf3 -s -p {port} > /tmp/iperf3_s_{port}.log 2>&1 &")

    time.sleep(2)

    # num_clients개의 클라이언트를 각기 다른 포트로 연결
    info(f"*** Start {num_clients} concurrent iperf3 clients\n")
    for i, c in enumerate(clients):
        port = 5201 + i
        host_num = i + 2
        logFile = f"/tmp/iperf3_h{host_num}_{cc_algo}.json"
        cmd = f"iperf3 -J -c {server_ip} -p {port} -t {duration} > {logFile} &"
        info(f"h{host_num}: iperf3 -c {server_ip}:{port}\n")
        c.cmd(cmd)
        time.sleep(0.1)

    info(f"*** Running {duration} seconds...\n")
    time.sleep(duration + 5)

    info("*** iperf3 finished. You can now run the analyzer script.\n")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel('info')
    import sys
    
    cc_algo = sys.argv[1] if len(sys.argv) > 1 else 'reno'
    runExperiment(cc_algo, duration=10, num_clients=20)
